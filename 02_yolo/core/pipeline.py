"""Module 02: canonical PreparedFrame -> original-pixel ObjectFrame."""

import logging
from pathlib import Path
from threading import RLock
from time import perf_counter
from typing import Self

from yolo.core import contracts
from yolo.core.config import load_config, validate_config
from yolo.core.contracts import ConfigurationError, DetectionFrame, DetectorConfig
from yolo.core.contracts import InputFrame as PreparedFrame
from yolo.core.detector import (
    NullDetector,
    ObjectDetector,
    UltralyticsYoloDetector,
    filter_detections,
)
from yolo.core.postprocess import clamp_source_box
from yolo.input_validation import input_error
from yolo.semantic.worker import SemanticWorker
from yolo.visualization.renderer import FrameRenderer

LOGGER = logging.getLogger("yolo.pipeline")


class DetectorPipeline:
    """Synchronous stage; a lock serializes model lifecycle and frame processing.

    FrameProcessor owns sequencing and generic preparation. The stage checks
    only what inference/restoration require. Fatal startup errors propagate;
    a per-frame backend error produces ERROR with no partial detections.
    """

    def __init__(
        self,
        config: DetectorConfig,
        detector: ObjectDetector | None = None,
        *,
        types=contracts,
        semantic_config=None,
        verifier=None,
    ):
        self.types = types
        self.config = validate_config(config)
        if detector is not None:
            self.detector = detector
        elif self.config.backend == "ultralytics":
            self.detector = UltralyticsYoloDetector(self.config, types=types)
        elif self.config.backend == "mock":
            raise ConfigurationError(
                "mock backend requires an explicitly injected detector"
            )
        else:
            self.detector = NullDetector()
        self._initialized = False
        self._reset_pending = False
        self._runtime_failed = False
        self._lock = RLock()
        self.semantic = SemanticWorker(semantic_config, verifier)

    @classmethod
    def from_yaml(
        cls, path: str | Path, detector: ObjectDetector | None = None
    ) -> "DetectorPipeline":
        return cls(load_config(path), detector)

    def initialize(self) -> None:
        InitializationError = self.types.InitializationError
        with self._lock:
            if not self._initialized:
                try:
                    self.detector.initialize()
                except Exception as exc:
                    LOGGER.error("YOLO initialization failed: %s", exc)
                    try:
                        self.detector.close()
                    except Exception as cleanup_error:  # noqa: BLE001 -- preserve original startup failure
                        exc.add_note(f"backend cleanup also failed: {cleanup_error}")
                    if isinstance(exc, InitializationError):
                        raise
                    raise InitializationError(
                        f"detector initialization failed: {exc}"
                    ) from exc
                self._initialized = True

    def close(self) -> None:
        with self._lock:
            self.semantic.close()
            try:
                self.detector.close()
            finally:
                self._initialized = False

    def reset(self) -> None:
        """New stream/reference shape: reset replaceable tracking, keep model if possible."""
        with self._lock:
            self.semantic.reset()
            if hasattr(self.detector, "reset_tracking"):
                self.detector.reset_tracking()
            else:
                try:
                    self.detector.close()
                finally:
                    self._initialized = False
            self._reset_pending = False

    def process(self, prepared: PreparedFrame) -> DetectionFrame:
        with self._lock:
            if not isinstance(prepared, PreparedFrame):
                raise TypeError("DetectorPipeline consumes Module 02 InputFrame")
            if prepared.reset_required:
                self.semantic.reset()
            output = self._process(prepared)
            self.semantic.observe(prepared, output)
            return output

    @property
    def semantic_result(self):
        return self.semantic.latest

    def render(self, prepared, objects):
        return FrameRenderer().render(
            prepared.source,
            objects,
            self.semantic_result,
            vlm_status=self.semantic.status,
            tracking=self.config.tracking,
        )

    def _report_failure(self, stage: str, frame_id: int, exc: Exception) -> None:
        """One warning per failure episode; repeated failures remain debug logs."""
        if not self._runtime_failed:
            LOGGER.warning("YOLO %s failed on frame %s: %s", stage, frame_id, exc)
        else:
            LOGGER.debug("YOLO %s still failing on frame %s: %s", stage, frame_id, exc)
        self._runtime_failed = True

    def _process(self, prepared: PreparedFrame) -> DetectionFrame:
        ObjectFrame = self.types.ResultFrame
        Detection = self.types.Detection
        Diagnostic = self.types.Diagnostic
        WarningCode = self.types.WarningCode
        NoticeCode = self.types.NoticeCode
        ModuleStatus = self.types.ModuleStatus
        if not isinstance(prepared, PreparedFrame):
            raise TypeError("YoloPipeline consumes shared.schemas.PreparedFrame")
        source = prepared.source
        if source is None:
            raise ValueError("PreparedFrame must retain its source")
        result = ObjectFrame(
            source.frame_id,
            source.timestamp_s,
            source.width,
            source.height,
            source_id=source.source_id,
            session_id=source.session_id,
            warnings=list(prepared.warnings),
            notices=list(prepared.notices),
        )
        if prepared.status in (ModuleStatus.INVALID_INPUT, ModuleStatus.ERROR):
            result.status = ModuleStatus.INVALID_INPUT
            result.stage_timings_ms["object_detection_ms"] = 0.0
            return result
        problem = input_error(prepared)
        if problem is not None:
            result.status = ModuleStatus.INVALID_INPUT
            result.warnings.append(
                Diagnostic(
                    WarningCode.INVALID_FRAME,
                    {"stage": "yolo_input", "reason": problem},
                )
            )
            result.stage_timings_ms["object_detection_ms"] = 0.0
            return result
        if prepared.reset_required:
            self._reset_pending = True
        if self._reset_pending:
            reset_started = perf_counter()
            try:
                self.reset()
            except Exception as exc:  # noqa: BLE001 -- isolate replaceable tracker reset as a structured frame failure
                result.status = ModuleStatus.ERROR
                result.warnings.append(
                    Diagnostic(
                        WarningCode.DETECTOR_FAILURE,
                        {
                            "stage": "tracker_reset",
                            "error": type(exc).__name__,
                            "message": str(exc),
                        },
                    )
                )
                result.stage_timings_ms["object_detection_ms"] = (
                    perf_counter() - reset_started
                ) * 1000
                self._report_failure("tracker_reset", source.frame_id, exc)
                return result
        # Initialization/configuration errors are fatal, outside runtime recovery.
        self.initialize()
        started = perf_counter()
        try:
            try:
                raw = self.detector.detect(prepared.image)
            finally:
                # A failed CPU retry can still emit a warning. Drain it on this
                # frame so it cannot incorrectly degrade the next healthy frame.
                if hasattr(self.detector, "pop_warnings"):
                    for warning in self.detector.pop_warnings():
                        if isinstance(warning, Diagnostic):
                            result.warnings.append(warning)
                        elif warning == "detector_cpu_fallback":
                            result.warnings.append(Diagnostic(WarningCode.CPU_FALLBACK))
                        else:
                            raise ValueError(
                                "backend returned an unsupported warning contract"
                            )
            candidates, invalid = filter_detections(
                raw,
                prepared.image.shape[:2],
                self.config,
                result.warnings,
                types=self.types,
            )
            for candidate in candidates:
                restored = prepared.source_detection(candidate)
                # No downstream stabilization/reference fields leak from reused backend leaves.
                result.detections.append(
                    Detection(
                        restored.class_id,
                        restored.class_name,
                        restored.confidence,
                        clamp_source_box(
                            restored.bbox, source.width, source.height, types=self.types
                        ),
                        restored.track_id,
                        identity_persistent=restored.track_id is not None,
                    )
                )
            if invalid:
                result.warnings.append(
                    Diagnostic(
                        WarningCode.INVALID_OBSERVATION,
                        {"count": invalid, "stage": "detector"},
                    )
                )
            result.status = (
                ModuleStatus.DEGRADED
                if result.warnings
                else ModuleStatus.OK
                if result.detections
                else ModuleStatus.NO_DETECTION
            )
        except Exception as exc:  # noqa: BLE001 -- isolate replaceable backend failures without partial output
            result.detections = []
            result.status = ModuleStatus.ERROR
            result.warnings.append(
                Diagnostic(
                    WarningCode.DETECTOR_FAILURE,
                    {"error": type(exc).__name__, "message": str(exc)},
                )
            )
            self._report_failure("inference", source.frame_id, exc)
        else:
            if self._runtime_failed:
                LOGGER.info("YOLO inference recovered on frame %s", source.frame_id)
                self._runtime_failed = False
        if any(d.track_id is None for d in result.detections):
            result.notices.append(
                Diagnostic(
                    NoticeCode.OBJECT_IDENTITY_UNAVAILABLE
                    if self.config.tracking
                    else NoticeCode.OBJECT_TRACKING_DISABLED
                )
            )
        if self.config.backend == "none":
            result.notices.append(Diagnostic(NoticeCode.DETECTOR_DISABLED))
        result.stage_timings_ms["object_detection_ms"] = (
            perf_counter() - started
        ) * 1000
        return result

    def __enter__(self) -> Self:
        self.initialize()
        return self

    def __exit__(self, *args) -> None:
        self.close()
