"""Module 02 stage: PreparedFrame -> authoritative ObjectFrame."""

from copy import deepcopy
from time import perf_counter

from yolo.inference.detector import (
    NullDetector,
    ObjectDetector,
    UltralyticsYoloDetector,
    filter_detections,
)

from shared.config import DetectorConfig
from shared.diagnostics import Diagnostic, NoticeCode, WarningCode
from shared.enums.module_status import ModuleStatus
from shared.schemas.object_frame import ObjectFrame
from shared.schemas.prepared_frame import PreparedFrame


class YoloPipeline:
    def __init__(self, config: DetectorConfig, detector: ObjectDetector | None = None):
        self.config = config
        if detector is not None:
            self.detector = detector
        elif config.backend == "ultralytics":
            self.detector = UltralyticsYoloDetector(config)
        elif config.backend == "mock":
            from integration.mocks import MockDetector

            self.detector = MockDetector()
        else:
            self.detector = NullDetector()
        self._initialized = False

    def initialize(self):
        if not self._initialized:
            self.detector.initialize()
            self._initialized = True

    def close(self):
        try:
            self.detector.close()
        finally:
            self._initialized = False

    def process(self, prepared: PreparedFrame) -> ObjectFrame:
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
        )
        if prepared.status == ModuleStatus.INVALID_INPUT:
            result.status = ModuleStatus.INVALID_INPUT
            result.warnings = list(prepared.warnings)
            return result
        if prepared.reset_required:
            self.close()
        self.initialize()
        started = perf_counter()
        try:
            raw = self.detector.detect(prepared.image)
            result.detections, invalid = filter_detections(
                [prepared.source_detection(d) for d in deepcopy(raw)],
                (source.height, source.width),
                self.config,
            )
            for d in result.detections:
                d.identity_persistent = d.track_id is not None
            if invalid:
                result.warnings.append(
                    Diagnostic(
                        WarningCode.INVALID_OBSERVATION,
                        {"count": invalid, "stage": "detector"},
                    )
                )
            if hasattr(self.detector, "pop_warnings"):
                for warning in self.detector.pop_warnings():
                    result.warnings.append(
                        warning
                        if isinstance(warning, Diagnostic)
                        else Diagnostic(WarningCode.CPU_FALLBACK)
                    )
            result.status = (
                ModuleStatus.DEGRADED
                if result.warnings
                else ModuleStatus.OK
                if result.detections
                else ModuleStatus.NO_DETECTION
            )
        except Exception as exc:  # noqa: BLE001 -- isolate replaceable backend failure as structured runtime diagnostics
            result.status = ModuleStatus.ERROR
            result.warnings.append(
                Diagnostic(
                    WarningCode.DETECTOR_FAILURE,
                    {"error": type(exc).__name__, "message": str(exc)},
                )
            )
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
