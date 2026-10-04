"""Frame-to-observation pipeline; no camera, GUI, HAR or procedure ownership."""

from __future__ import annotations

import logging
from collections.abc import Callable
from copy import deepcopy
from pathlib import Path
from threading import RLock
from time import perf_counter
from typing import Self, TypeVar

import cv2

from perception.associations import associate
from perception.config import PerceptionConfig
from perception.contracts import (
    CoordinateFrame,
    FramePacket,
    PerceptionFrameResult,
    ReferenceFrameInfo,
)
from perception.coordinate_frame import (
    CoordinateTransformer,
    ManualRackTransformer,
    UnavailableReference,
)
from perception.detector import (
    InitializationError,
    NullDetector,
    ObjectDetector,
    UltralyticsYoloDetector,
    filter_detections,
)
from perception.hand_tracker import (
    HandTracker,
    MediaPipeHandTracker,
    NullHandTracker,
    filter_hands,
)
from perception.interaction import interaction_candidates
from perception.mocks import MockDetector, MockHandTracker
from perception.pose_tracker import NullPoseTracker, PoseTracker
from perception.preprocessing import InvalidFrameError, preprocess
from perception.stabilizer import PerceptionStabilizer
from perception.utils import valid_point, valid_score
from shared.enums.module_status import ModuleStatus

LOGGER = logging.getLogger(__name__)
T = TypeVar("T")
STAGES = (
    "preprocessing_ms",
    "object_detection_ms",
    "hand_tracking_ms",
    "pose_tracking_ms",
    "coordinate_transform_ms",
    "association_ms",
    "stabilization_ms",
)


class PerceptionPipeline:
    """One ordered source per instance, safe for a dedicated processing worker.

    Calls are serialized by a lock; no application thread is created. Input
    frame IDs and monotonic timestamps must strictly increase. Use reset() for
    another stream/session. Initialization errors raise; runtime failures return
    typed observations with warnings. Inputs and injected results are copied.
    """

    def __init__(
        self,
        config: PerceptionConfig | None = None,
        *,
        detector: ObjectDetector | None = None,
        hand_tracker: HandTracker | None = None,
        pose_tracker: PoseTracker | None = None,
        coordinate_transformer: CoordinateTransformer | None = None,
    ):
        self.config = deepcopy(config or PerceptionConfig())
        self.config.validate()
        d, h, r = (
            self.config.detector,
            self.config.hand_tracker,
            self.config.reference_frame,
        )
        self.detector = (
            detector
            if detector is not None
            else (
                UltralyticsYoloDetector(d)
                if d.backend == "ultralytics"
                else MockDetector()
                if d.backend == "mock"
                else NullDetector()
            )
        )
        self.hand_tracker = (
            hand_tracker
            if hand_tracker is not None
            else (
                NullHandTracker()
                if not h.enabled or h.backend == "none"
                else MediaPipeHandTracker(h)
                if h.backend == "mediapipe"
                else MockHandTracker()
            )
        )
        self.pose_tracker = (
            pose_tracker if pose_tracker is not None else NullPoseTracker()
        )
        self.coordinate_transformer = (
            coordinate_transformer
            if coordinate_transformer is not None
            else (
                ManualRackTransformer(r.corners_normalized or [], r.reference_id)
                if r.enabled
                else UnavailableReference()
            )
        )
        self._lock = RLock()
        self._initialized = False
        self._closed = False
        self._stabilizer = PerceptionStabilizer(
            self.config.stabilization, self.config.interaction
        )
        self._source_id: str | None = None
        self._last_id: int | None = None
        self._last_timestamp: float | None = None
        self._last_shape: tuple[int, int] | None = None
        self._reference_context: tuple[bool, str | None] | None = None

    @classmethod
    def from_yaml(cls, path: str | Path, **backends) -> PerceptionPipeline:
        return cls(PerceptionConfig.from_yaml(path), **backends)

    def initialize(self) -> None:
        """Load local models. Roll back all acquired resources on failure."""
        with self._lock:
            if self._closed:
                raise InitializationError(
                    "pipeline is closed; call reset() to start a new session"
                )
            if self._initialized:
                return
            try:
                for backend in (self.detector, self.hand_tracker, self.pose_tracker):
                    backend.initialize()
            except Exception as exc:
                self._close_backends()
                if isinstance(exc, InitializationError):
                    raise
                raise InitializationError(
                    f"perception initialization failed: {exc}"
                ) from exc
            self._initialized = True
            LOGGER.info("Perception pipeline initialized")

    def _close_backends(self) -> None:
        for backend in (self.pose_tracker, self.hand_tracker, self.detector):
            try:
                backend.close()
            except Exception:
                LOGGER.exception("Backend close failed")
        self._initialized = False

    def close(self) -> None:
        """Idempotently release owned model resources."""
        with self._lock:
            self._close_backends()
            self._closed = True
            self._stabilizer.reset()

    def reset(self) -> None:
        """Release backend tracking state and allow a new source/session."""
        with self._lock:
            self._close_backends()
            self._closed = False
            self._source_id = self._last_id = self._last_timestamp = (
                self._last_shape
            ) = None
            self._reference_context = None
            self._stabilizer.reset()

    def __enter__(self) -> Self:
        self.initialize()
        return self

    def __exit__(self, exc_type, exc_value, traceback) -> None:
        self.close()

    def process(self, packet: FramePacket) -> PerceptionFrameResult:
        """Convert a shared FramePacket to normalized structured observations."""
        with self._lock:
            started = perf_counter()
            result = PerceptionFrameResult(
                packet.frame_id,
                packet.timestamp_s,
                packet.source_id,
                stage_timings_ms=dict.fromkeys(STAGES, 0.0),
            )

            def timed(name: str, action: Callable[[], T]) -> T:
                stage_started = perf_counter()
                try:
                    return action()
                finally:
                    result.stage_timings_ms[name] += (
                        perf_counter() - stage_started
                    ) * 1000

            def finish() -> PerceptionFrameResult:
                result.processing_time_ms = (perf_counter() - started) * 1000
                result.stage_timings_ms["total_ms"] = result.processing_time_ms
                return result

            def invalid(
                warning: str, reset_history: bool = False
            ) -> PerceptionFrameResult:
                result.status = ModuleStatus.INVALID_INPUT
                result.warnings.append(warning)
                if reset_history:
                    self._stabilizer.reset()
                    result.warnings.append("temporal_history_reset")
                return finish()

            try:
                processed = timed(
                    "preprocessing_ms",
                    lambda: preprocess(packet, self.config.preprocessing),
                )
            except (
                InvalidFrameError,
                ValueError,
                TypeError,
                OverflowError,
                cv2.error,
            ) as exc:
                return invalid(f"invalid_frame: {exc}", True)
            result.image_width, result.image_height = packet.width, packet.height
            if packet.status in (ModuleStatus.ERROR, ModuleStatus.INVALID_INPUT):
                return invalid("upstream_frame_invalid", True)
            if self._source_id is not None and packet.source_id != self._source_id:
                return invalid(
                    "source_changed: call reset() before processing another source"
                )
            if self._last_id is not None:
                assert self._last_timestamp is not None
                if (
                    packet.frame_id <= self._last_id
                    or packet.timestamp_s <= self._last_timestamp
                ):
                    return invalid(
                        "non_monotonic_frame: frame_id and timestamp_s must strictly increase"
                    )
            self.initialize()  # Critical failure deliberately raises to the caller.
            shape = (packet.height, packet.width)
            if self._last_id is not None:
                assert self._last_timestamp is not None
                gap = packet.frame_id - self._last_id - 1
                time_gap = packet.timestamp_s - self._last_timestamp
                if (
                    self._last_shape != shape
                    or time_gap > self.config.stabilization.max_time_gap_s
                ):
                    self._stabilizer.reset()
                    result.warnings.append("temporal_history_reset")
                elif gap > 0:
                    self._stabilizer.age_missing(gap)
                    result.warnings.append(f"source_frames_missing: {gap}")
            self._source_id = packet.source_id
            self._last_id, self._last_timestamp, self._last_shape = (
                packet.frame_id,
                packet.timestamp_s,
                shape,
            )

            try:

                def detect():
                    raw = deepcopy(self.detector.detect(processed.image.copy()))
                    source = [processed.source_detection(d) for d in raw]
                    return filter_detections(source, shape, self.config.detector)

                result.detections, invalid_count = timed("object_detection_ms", detect)
                if invalid_count:
                    result.warnings.append(
                        f"invalid_detections_filtered: {invalid_count}"
                    )
            except Exception as exc:
                LOGGER.exception("Object inference failed")
                result.warnings.append(f"detector_failure: {type(exc).__name__}: {exc}")
            if hasattr(self.detector, "pop_warnings"):
                result.warnings.extend(self.detector.pop_warnings())

            try:

                def track_hands():
                    raw = deepcopy(self.hand_tracker.track(processed.image.copy()))
                    return filter_hands([processed.source_hand(h) for h in raw])

                result.hands, invalid_count = timed("hand_tracking_ms", track_hands)
                if invalid_count:
                    result.warnings.append(f"invalid_hands_filtered: {invalid_count}")
            except Exception as exc:
                LOGGER.exception("Hand inference failed")
                result.warnings.append(
                    f"hand_tracker_failure: {type(exc).__name__}: {exc}"
                )
            try:

                def track_poses():
                    raw = deepcopy(self.pose_tracker.track(processed.image.copy()))
                    poses = [processed.source_pose(p) for p in raw]
                    if any(
                        not valid_score(p.confidence)
                        or not all(valid_point(pt) for pt in p.landmarks)
                        for p in poses
                    ):
                        raise ValueError("invalid pose observation")
                    return poses

                result.poses = timed("pose_tracking_ms", track_poses)
            except Exception as exc:
                LOGGER.exception("Pose inference failed")
                result.warnings.append(
                    f"pose_tracker_failure: {type(exc).__name__}: {exc}"
                )

            def transform():
                source_bgr = (
                    cv2.cvtColor(packet.image, cv2.COLOR_RGB2BGR)
                    if packet.color_format == "RGB"
                    else packet.image.copy()
                )
                info = self.coordinate_transformer.update(source_bgr)
                if not info.valid:
                    return info
                if not info.reference_id:
                    raise ValueError("valid reference requires a stable reference_id")
                convert = lambda point: self.coordinate_transformer.image_to_reference(
                    point, shape
                )
                for d in result.detections:
                    d.reference_polygon = tuple(convert(p) for p in d.bbox.corners)
                    if not all(valid_point(p) for p in d.reference_polygon):
                        raise ValueError("nonfinite transformed detection")
                for h in result.hands:
                    h.reference_landmarks = [convert(p) for p in h.landmarks]
                    h.reference_palm_center = convert(h.palm_center)
                    if not all(
                        valid_point(p)
                        for p in h.reference_landmarks + [h.reference_palm_center]
                    ):
                        raise ValueError("nonfinite transformed hand")
                for p in result.poses:
                    p.reference_landmarks = [convert(pt) for pt in p.landmarks]
                    if not all(valid_point(pt) for pt in p.reference_landmarks):
                        raise ValueError("nonfinite transformed pose")
                return info

            try:
                result.reference_frame = timed("coordinate_transform_ms", transform)
                result.coordinate_frame_valid = result.reference_frame.valid
            except Exception as exc:
                LOGGER.warning("Reference unavailable: %s", exc, exc_info=True)
                result.warnings.append(
                    f"reference_frame_failure: {type(exc).__name__}: {exc}"
                )
                result.reference_frame = ReferenceFrameInfo()
            if not result.coordinate_frame_valid:
                result.warnings.append("reference_frame_unavailable")
                for d in result.detections:
                    d.reference_polygon = None
                for h in result.hands:
                    h.reference_landmarks = h.reference_palm_center = None
                for p in result.poses:
                    p.reference_landmarks = None
            result.association_coordinate_frame = (
                CoordinateFrame.RACK_RELATIVE
                if result.coordinate_frame_valid
                else CoordinateFrame.NORMALIZED_IMAGE
            )
            context = (
                result.coordinate_frame_valid,
                result.reference_frame.reference_id,
            )
            if context != self._reference_context:
                self._stabilizer.reset_geometry()
                self._reference_context = context

            try:
                timed(
                    "stabilization_ms",
                    lambda: self._stabilizer.update_observations(
                        result.detections,
                        result.hands,
                        shape,
                        packet.timestamp_s,
                        result.coordinate_frame_valid,
                    ),
                )
                result.associations = timed(
                    "association_ms",
                    lambda: associate(
                        result.hands,
                        result.detections,
                        shape,
                        self.config.interaction,
                        result.coordinate_frame_valid,
                    ),
                )

                def stabilize():
                    self._stabilizer.update_trends(result.associations)
                    candidates = interaction_candidates(
                        result.detections, result.hands, result.associations
                    )
                    return self._stabilizer.update_interactions(
                        candidates, result.detections
                    )

                result.interactions = timed("stabilization_ms", stabilize)
            except Exception as exc:
                LOGGER.exception("Geometry/stabilization failed")
                result.associations = []
                result.interactions = []
                self._stabilizer.reset()
                result.warnings.append(f"geometry_failure: {type(exc).__name__}: {exc}")
            if not result.detections:
                result.warnings.append("no_objects")
            if not result.hands and self.config.hand_tracker.enabled:
                result.warnings.append("no_hands")
            if any(a.ambiguous for a in result.associations):
                result.warnings.append("ambiguous_hand_object_association")
            if any(d.track_id is None for d in result.detections):
                result.warnings.append("persistent_object_identity_unavailable")
            if any(h.confidence is None for h in result.hands):
                result.warnings.append("hand_confidence_unavailable")
            if packet.status != ModuleStatus.OK:
                result.warnings.append(f"upstream_status: {packet.status.value}")
            if result.warnings:
                result.status = ModuleStatus.DEGRADED
            if (
                not result.detections
                and not result.hands
                and not any("failure" in w for w in result.warnings)
            ):
                result.status = ModuleStatus.NO_DETECTION
            return finish()
