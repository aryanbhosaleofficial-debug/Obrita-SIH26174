"""Object detection interface and local-only Ultralytics adapter."""

from __future__ import annotations

import logging
import os
from dataclasses import replace
from importlib.util import find_spec
from numbers import Real
from threading import RLock
from typing import Any, Protocol

import numpy as np
import yaml
from yolo.config import validate_config, validate_tracker
from yolo.inference.postprocess import parse_results

from shared.config import DetectorConfig
from shared.diagnostics import Diagnostic, WarningCode
from shared.errors import InitializationError
from shared.schemas.observations import BoundingBox, Detection
from shared.utils.observation import valid_score

LOGGER = logging.getLogger(__name__)


class ObjectDetector(Protocol):
    """Input uint8 BGR; boxes in input-image pixels; never raw model results."""

    def initialize(self) -> None: ...
    def detect(self, image: np.ndarray) -> list[Detection]: ...
    def close(self) -> None: ...


class NullDetector:
    def initialize(self) -> None:
        pass

    def detect(self, image: np.ndarray) -> list[Detection]:
        return []

    def close(self) -> None:
        pass


def filter_detections(
    detections: list[Detection],
    shape: tuple[int, int],
    config: DetectorConfig,
    diagnostics: list[Diagnostic] | None = None,
) -> tuple[list[Detection], int]:
    """Threshold, whitelist, finite/positive boxes and diagnostic input clipping.

    Partially outside boxes are intersected with the input image and reported;
    wholly outside boxes are rejected. Output geometry uses Python floats.
    """
    height, width = shape
    output = []
    invalid = 0
    clipped = 0
    seen_tracks: set[int] = set()
    for detection in detections:
        if not isinstance(detection, Detection) or not isinstance(
            detection.bbox, BoundingBox
        ):
            invalid += 1
            continue
        b = detection.bbox
        if (
            not valid_score(detection.confidence)
            or detection.confidence is None
            or type(detection.class_id) is not int
            or detection.class_id < 0
            or not isinstance(detection.class_name, str)
            or not detection.class_name
            or not all(
                isinstance(v, Real)
                and not isinstance(v, (bool, np.bool_))
                and np.isfinite(v)
                for v in (b.x1, b.y1, b.x2, b.y2)
            )
            or b.x2 <= b.x1
            or b.y2 <= b.y1
            or (
                detection.track_id is not None
                and (type(detection.track_id) is not int or detection.track_id < 0)
            )
        ):
            invalid += 1
            continue
        if detection.confidence < config.confidence_threshold:
            continue
        if (
            config.class_whitelist is not None
            and detection.class_id not in config.class_whitelist
        ):
            continue
        box = BoundingBox(
            float(max(0.0, min(width, b.x1))),
            float(max(0.0, min(height, b.y1))),
            float(max(0.0, min(width, b.x2))),
            float(max(0.0, min(height, b.y2))),
        )
        if box.x2 <= box.x1 or box.y2 <= box.y1:
            invalid += 1
            continue
        if detection.track_id is not None:
            if detection.track_id in seen_tracks:
                invalid += 1
                continue
            seen_tracks.add(detection.track_id)
        clipped += box != b
        output.append(
            replace(detection, bbox=box, confidence=float(detection.confidence))
        )
    if clipped and diagnostics is not None:
        diagnostics.append(
            Diagnostic(
                WarningCode.INVALID_OBSERVATION,
                {"stage": "detector", "clipped_count": clipped},
            )
        )
    if invalid or clipped:
        LOGGER.debug("YOLO observations rejected=%s clipped=%s", invalid, clipped)
    return output, invalid


class UltralyticsYoloDetector:
    """Lazy model instance; requires existing .pt or .onnx path, never downloads.

    Optional tracking requires a local tracker YAML with ReID disabled. The
    stage binds a single stream; upstream reset signals clear tracker history
    without reloading model weights.
    CPU fallback is permitted only for accelerator-related failures.
    """

    def __init__(self, config: DetectorConfig):
        self.config = validate_config(config)
        self._lock = RLock()
        self._model: Any = None
        self._device = "cpu"
        self._warnings: list[str | Diagnostic] = []
        self._class_names: dict[int, str] | None = None

    def pop_warnings(self) -> list[str | Diagnostic]:
        with self._lock:
            warnings, self._warnings = self._warnings, []
            return warnings

    def initialize(self) -> None:
        with self._lock:
            self._initialize()

    def _initialize(self) -> None:
        if self._model is not None:
            return
        self._warnings.clear()
        path = self.config.model_path
        if path is None or not path.is_file():
            raise InitializationError(
                f"YOLO model file not found: {path}; supply local trained weights"
            )
        if path.suffix.lower() not in (".pt", ".onnx"):
            raise InitializationError(
                "prototype adapter supports local .pt and .onnx models"
            )
        if self.config.tracking:
            tracker_path = self.config.tracker_path
            if tracker_path is None or not tracker_path.is_file():
                raise InitializationError(
                    "tracking requires an existing local tracker_path YAML"
                )
            try:
                with tracker_path.open(encoding="utf-8") as stream:
                    tracker = yaml.safe_load(stream)
            except (OSError, yaml.YAMLError) as exc:
                raise InitializationError(
                    f"cannot read local tracker YAML {tracker_path}: {exc}"
                ) from exc
            if (
                not isinstance(tracker, dict)
                or tracker.get("tracker_type") not in ("bytetrack", "botsort")
                or tracker.get("with_reid", False) is not False
            ):
                raise InitializationError(
                    "offline tracking supports bytetrack/botsort with with_reid: false"
                )
        try:
            from yolo.inference.class_map import load_class_map, validate_model_classes

            expected_classes = load_class_map(self.config.classes_path)
            if (
                self.config.class_whitelist is not None
                and not set(self.config.class_whitelist) <= expected_classes.keys()
            ):
                raise InitializationError(
                    "class_whitelist contains IDs absent from the project class mapping"
                )
            if self.config.tracking and find_spec("lap") is None:
                raise InitializationError(
                    "tracking requires local lap>=0.5.12; install requirements-perception-inference.txt before offline use"
                )
            if self.config.tracking:
                validate_tracker(tracker)
            # Ultralytics reads these flags at import time. Require callers that
            # already imported it to use the same offline policy, instead of
            # monkey-patching process-global library state.
            os.environ.setdefault("YOLO_AUTOINSTALL", "false")
            os.environ.setdefault("YOLO_OFFLINE", "true")
            if os.environ["YOLO_OFFLINE"].lower() != "true":
                raise InitializationError(
                    "launch with YOLO_OFFLINE=true before importing Ultralytics"
                )
            import torch
            from ultralytics import YOLO
            from ultralytics.utils import checks

            if checks.AUTOINSTALL:
                raise InitializationError(
                    "Ultralytics auto-install is enabled; launch with YOLO_AUTOINSTALL=false and YOLO_OFFLINE=true before importing it"
                )
            if getattr(checks, "ONLINE", False):
                raise InitializationError(
                    "Ultralytics was imported with online checks enabled; restart with "
                    "YOLO_OFFLINE=true before importing it"
                )
            if path.suffix.lower() == ".onnx":
                import onnxruntime  # noqa: F401 -- never install it at runtime
            requested = self.config.device
            cuda_available = torch.cuda.is_available()
            mps_available = (
                hasattr(torch.backends, "mps") and torch.backends.mps.is_available()
            )
            if requested == "auto":
                self._device = "0" if cuda_available else "cpu"
            elif requested == "cpu":
                self._device = "cpu"
            elif requested == "mps" and mps_available:
                self._device = requested
            elif requested != "mps" and cuda_available:
                count = (
                    torch.cuda.device_count()
                    if hasattr(torch.cuda, "device_count")
                    else 1
                )
                if int(requested) >= count:
                    raise InitializationError(
                        f"CUDA device {requested} does not exist; {count} local devices available"
                    )
                self._device = requested
            elif self.config.cpu_fallback:
                self._device = "cpu"
                self._warnings.append("detector_cpu_fallback")
            else:
                raise InitializationError(
                    f"requested accelerator unavailable: {requested}"
                )
            self._model = YOLO(str(path), task="detect")
            # Exported models may initialize a backend while reading names.
            # Make that initialization use the selected device as well.
            if isinstance(getattr(self._model, "overrides", None), dict):
                self._model.overrides["device"] = self._device
            validate_model_classes(self._model.names, expected_classes)
            self._class_names = expected_classes
            LOGGER.info(
                "YOLO initialized with local model %s on %s", path, self._device
            )
        except InitializationError:
            self._model = None
            self._class_names = None
            self._warnings.clear()
            raise
        except Exception as exc:
            self._model = None
            self._class_names = None
            self._warnings.clear()
            raise InitializationError(f"YOLO initialization failed: {exc}") from exc

    def _infer(self, image: np.ndarray):
        kwargs = {
            "source": image,
            "conf": self.config.confidence_threshold,
            "iou": self.config.iou_threshold,
            "classes": self.config.class_whitelist,
            "device": self._device,
            "verbose": False,
            "save": False,
        }
        if self.config.tracking:
            return self._model.track(
                **kwargs, persist=True, tracker=str(self.config.tracker_path)
            )
        return self._model.predict(**kwargs)

    def detect(self, image: np.ndarray) -> list[Detection]:
        with self._lock:
            return self._detect(image)

    def _detect(self, image: np.ndarray) -> list[Detection]:
        if self._model is None:
            self.initialize()
        try:
            results = self._infer(image)
        except Exception as exc:
            accelerator_error = any(
                word in str(exc).lower()
                for word in ("cuda", "cudnn", "mps", "device", "out of memory")
            )
            if (
                self._device == "cpu"
                or not self.config.cpu_fallback
                or not accelerator_error
            ):
                raise
            LOGGER.warning("Accelerator inference failed; retrying on CPU: %s", exc)
            self._device = "cpu"
            if (
                self.config.model_path is not None
                and self.config.model_path.suffix.lower() == ".onnx"
            ):
                self._model.predictor = None  # recreate exported-runtime backend on CPU
            else:
                self._model.to("cpu")
            self._warnings.append("detector_cpu_fallback")
            results = self._infer(image)
        output, invalid = parse_results(
            results, image.shape[:2], self._class_names, self.config.tracking
        )
        if invalid:
            self._warnings.append(
                Diagnostic(
                    WarningCode.INVALID_OBSERVATION,
                    {"stage": "yolo_result", "count": invalid},
                )
            )
        return output

    def reset_tracking(self) -> None:
        """Reset backend tracker histories without reloading local model weights."""
        with self._lock:
            predictor = getattr(self._model, "predictor", None)
            for tracker in getattr(predictor, "trackers", ()):
                tracker.reset()
            if predictor is not None and hasattr(predictor, "vid_path"):
                predictor.vid_path = [None] * len(predictor.vid_path)
            self._warnings.clear()

    def close(self) -> None:
        with self._lock:
            self._model = None
            self._class_names = None
            self._warnings.clear()
