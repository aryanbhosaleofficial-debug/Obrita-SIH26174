"""Image-free Module 03 API. One ordered stream per instance; no implicit threads."""

import logging
from dataclasses import dataclass, replace

from optimization.input.input_validator import (
    OptimizationInputError,
    validate_object_frame,
)
from optimization.output.optimization_packet_builder import build_optimization_packet
from optimization.temporal.sequence_buffer import SequenceBuffer
from optimization.temporal.stabilizer import PerceptionStabilizer
from optimization.temporal.temporal_filter import filter_detections

from shared.config import InteractionConfig, StabilizationConfig
from shared.diagnostics import Diagnostic, WarningCode
from shared.enums.module_status import ModuleStatus
from shared.schemas.object_frame import ObjectFrame
from shared.schemas.observations import Detection, OptimizationObservations
from shared.schemas.optimization_packet import OptimizationOutputPacket, TemporalFrame

logger = logging.getLogger(__name__)


@dataclass
class _Admission:
    detections: list[Detection]
    missing_frames: int
    filtered_count: int
    duplicate_count: int
    restarted: bool
    warnings: list[Diagnostic]


class OptimizationSequence:
    """Deterministic temporal evidence from the canonical YOLO ObjectFrame.

    The spatial OptimizationPipeline composes this SAME state machine and
    supplies existing hands/reference features before publication. The external
    PerceptionChain serializes calls; direct callers must do so themselves.
    """

    def __init__(
        self,
        config: StabilizationConfig | None = None,
        *,
        interaction: InteractionConfig | None = None,
    ):
        self.config = replace(config or StabilizationConfig())
        self.config.validate()
        self._stabilizer = PerceptionStabilizer(
            self.config, interaction or InteractionConfig()
        )
        self._buffer = SequenceBuffer(self.config.history_size)
        self.reset()
        logger.info("Optimization sequence initialized: %s", self.config)

    def reset(self) -> None:
        self._stabilizer.reset()
        self._buffer.clear()
        self._identity: tuple[str, str] | None = None
        self._shape: tuple[int, int] | None = None
        self._last_id: int | None = None
        self._timestamp: float | None = None
        logger.debug("Optimization sequence reset")

    def _begin(
        self,
        frame: ObjectFrame,
        *,
        missing_frames: int | None = None,
        reset_required: bool = False,
    ) -> _Admission:
        # Validate everything before advancing the cursor or touching histories.
        validate_object_frame(frame, self.config.max_detections_per_frame)
        identity = (frame.source_id, frame.session_id)
        if self._identity is not None and identity != self._identity:
            raise OptimizationInputError("source/session changed; call reset() first")
        if (self._last_id is not None and frame.frame_id <= self._last_id) or (
            self._timestamp is not None and frame.timestamp_s <= self._timestamp
        ):
            raise OptimizationInputError(
                "frame_id and timestamp_s must strictly increase"
            )
        shape = (frame.image_height, frame.image_width)
        gap = (
            max(0, frame.frame_id - self._last_id - 1)
            if missing_frames is None and self._last_id is not None
            else missing_frames or 0
        )
        restarted = reset_required or (
            self._shape is not None
            and (
                shape != self._shape
                or frame.timestamp_s - self._timestamp > self.config.max_time_gap_s
            )
        )
        warnings = []
        if restarted:
            # Explicit reset restarts IDs for reproducible replay. Automatic
            # discontinuities keep allocating new keys within this run.
            self._stabilizer.reset(preserve_counters=True)
            self._buffer.clear()
            warnings.append(Diagnostic(WarningCode.TEMPORAL_HISTORY_RESET))
            logger.debug("Temporal context restarted at frame=%s", frame.frame_id)
        elif gap:
            self._stabilizer.age_missing(gap)
        if gap:
            warnings.append(
                Diagnostic(WarningCode.SOURCE_FRAME_MISSING, {"count": gap})
            )
        detections, filtered, duplicates = filter_detections(frame, self.config)
        self._identity, self._shape = identity, shape
        self._last_id, self._timestamp = frame.frame_id, frame.timestamp_s
        return _Admission(detections, gap, filtered, duplicates, restarted, warnings)

    def _attach(
        self, packet: OptimizationOutputPacket, raw: ObjectFrame, admission: _Admission
    ) -> OptimizationOutputPacket:
        evidence = self._stabilizer.snapshot()
        packet.stable_detections = tuple(d for d in evidence if d.confirmed)
        packet.temporal_window = self._buffer.append(
            TemporalFrame(
                raw.frame_id,
                raw.timestamp_s,
                evidence,
                admission.missing_frames,
                raw.status,
            )
        )
        packet.raw_detection_count = len(raw.detections)
        packet.filtered_detection_count = admission.filtered_count
        packet.duplicate_detection_count = admission.duplicate_count
        return packet

    def process(self, frame: ObjectFrame) -> OptimizationOutputPacket:
        admission = self._begin(frame)
        detections = admission.detections
        self._stabilizer.update_observations(
            detections,
            [],
            (frame.image_height, frame.image_width),
            frame.timestamp_s,
            False,
            frame_id=frame.frame_id,
        )
        # Keep all ancillary state bounded if a caller previously used the
        # spatial wrapper; no semantic interaction is invented by this API.
        self._stabilizer.update_trends([], frame.timestamp_s)
        self._stabilizer.update_interactions([], detections)
        warnings = list(frame.warnings)
        warnings.extend(w for w in admission.warnings if w not in warnings)
        status = frame.status
        if status not in (ModuleStatus.ERROR, ModuleStatus.INVALID_INPUT):
            status = (
                ModuleStatus.DEGRADED
                if warnings or status == ModuleStatus.DEGRADED
                else ModuleStatus.OK
                if detections
                else ModuleStatus.NO_DETECTION
            )
        observations = OptimizationObservations(
            frame.frame_id,
            frame.timestamp_s,
            frame.source_id,
            image_width=frame.image_width,
            image_height=frame.image_height,
            detections=detections,
            session_id=frame.session_id,
            status=status,
            warnings=warnings,
            notices=list(frame.notices),
            stage_timings_ms=dict(frame.stage_timings_ms),
        )
        return self._attach(
            build_optimization_packet(frame, observations), frame, admission
        )
