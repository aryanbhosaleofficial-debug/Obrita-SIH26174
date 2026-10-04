"""Object detection interface and local-only Ultralytics adapter."""

from __future__ import annotations

import logging
import os
from dataclasses import replace
from typing import Any, Protocol

import numpy as np
import yaml

from perception.config import DetectorConfig
from perception.contracts import BoundingBox, Detection
from perception.utils import valid_score

LOGGER = logging.getLogger(__name__)


class InitializationError(RuntimeError):
    """Critical model/dependency initialization failure."""


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
    detections: list[Detection], shape: tuple[int, int], config: DetectorConfig
) -> tuple[list[Detection], int]:
    """Threshold, whitelist, finite/positive box validation and source clipping."""
    height, width = shape
    output = []
    invalid = 0
    seen_tracks: set[int] = set()
    for detection in detections:
        b = detection.bbox
        if (
            not valid_score(detection.confidence)
            or detection.confidence is None
            or type(detection.class_id) is not int
            or detection.class_id < 0
            or not isinstance(detection.class_name, str)
            or not detection.class_name
            or not np.isfinite([b.x1, b.y1, b.x2, b.y2]).all()
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
            max(0.0, min(width, b.x1)),
            max(0.0, min(height, b.y1)),
            max(0.0, min(width, b.x2)),
            max(0.0, min(height, b.y2)),
        )
        if box.x2 <= box.x1 or box.y2 <= box.y1:
            invalid += 1
            continue
        if detection.track_id is not None:
            if detection.track_id in seen_tracks:
                invalid += 1
                continue
            seen_tracks.add(detection.track_id)
        output.append(replace(detection, bbox=box))
    return output, invalid


class UltralyticsYoloDetector:
    """Lazy model instance; requires existing .pt or .onnx path, never downloads.

    Optional tracking requires a local tracker YAML with ReID disabled. The
    pipeline binds a single source and close/reinitialize resets tracker state.
    CPU fallback is permitted only for accelerator-related failures.
    """

    def __init__(self, config: DetectorConfig):
        self.config = config
        self._model: Any = None
        self._device = "cpu"
        self._warnings: list[str] = []

    def pop_warnings(self) -> list[str]:
        warnings, self._warnings = self._warnings, []
        return warnings

    def initialize(self) -> None:
        if self._model is not None:
            return
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
            with tracker_path.open(encoding="utf-8") as stream:
                tracker = yaml.safe_load(stream)
            if (
                not isinstance(tracker, dict)
                or tracker.get("tracker_type") not in ("bytetrack", "botsort")
                or tracker.get("with_reid", False) is not False
            ):
                raise InitializationError(
                    "offline tracking supports bytetrack/botsort with with_reid: false"
                )
        try:
            # Ultralytics reads these flags at import time. Require callers that
            # already imported it to use the same offline policy, instead of
            # monkey-patching process-global library state.
            os.environ.setdefault("YOLO_AUTOINSTALL", "false")
            os.environ.setdefault("YOLO_OFFLINE", "true")
            import torch
            from ultralytics import YOLO
            from ultralytics.utils import checks

            if checks.AUTOINSTALL:
                raise InitializationError(
                    "Ultralytics auto-install is enabled; launch with YOLO_AUTOINSTALL=false and YOLO_OFFLINE=true before importing it"
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
            elif (requested == "mps" and mps_available) or (
                requested != "mps" and cuda_available
            ):
                self._device = requested
            elif self.config.cpu_fallback:
                self._device = "cpu"
                self._warnings.append("detector_cpu_fallback")
            else:
                raise InitializationError(
                    f"requested accelerator unavailable: {requested}"
                )
            self._model = YOLO(str(path), task="detect")
            LOGGER.info(
                "YOLO initialized with local model %s on %s", path, self._device
            )
        except InitializationError:
            raise
        except Exception as exc:
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
        output = []
        for result in results:
            boxes = result.boxes
            if boxes is None:
                continue
            coordinates = boxes.xyxy.cpu().numpy()
            scores = boxes.conf.cpu().numpy()
            classes = boxes.cls.cpu().numpy()
            ids = (
                boxes.id.cpu().numpy()
                if self.config.tracking and boxes.id is not None
                else None
            )
            for index, (coords, score, class_id) in enumerate(
                zip(coordinates, scores, classes)
            ):
                cid = int(class_id)
                output.append(
                    Detection(
                        cid,
                        str(result.names[cid]),
                        float(score),
                        BoundingBox(*(float(v) for v in coords)),
                        int(ids[index]) if ids is not None else None,
                    )
                )
        return output

    def close(self) -> None:
        self._model = None
        self._warnings.clear()
