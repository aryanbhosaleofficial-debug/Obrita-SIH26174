"""Shared observation contracts. Image geometry uses original-source pixels.

Scores are evidence scores, never calibrated probabilities of physical contact.
Persistent identities are supplied only by a backend that actually tracks them.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

from shared.diagnostics import Diagnostic
from shared.enums.module_status import ModuleStatus
from shared.schemas.frame_packet import (
    FramePacket,  # noqa: F401 -- compatibility export
)


class CoordinateFrame(str, Enum):
    IMAGE_PIXELS = "image_pixels"
    NORMALIZED_IMAGE = "normalized_image"
    IMAGE_DIAGONAL = "image_diagonal"
    RACK_RELATIVE = "rack_relative"


class InteractionType(str, Enum):
    NEAR = "hand_near_object"
    CONTACT = "hand_contact_candidate"
    OVERLAP = "hand_object_overlap"
    LEAVING = "hand_leaving_object"
    MOTION = "object_motion_candidate"


class MotionState(str, Enum):
    UNKNOWN = "unknown"
    STATIONARY = "stationary"
    MOVING = "moving"


class DistanceTrend(str, Enum):
    UNKNOWN = "unknown"
    APPROACHING = "approaching"
    RETREATING = "retreating"
    STEADY = "steady"


@dataclass(frozen=True)
class Point2D:
    x: float
    y: float


@dataclass(frozen=True)
class BoundingBox:
    x1: float
    y1: float
    x2: float
    y2: float

    @property
    def center(self) -> Point2D:
        return Point2D((self.x1 + self.x2) / 2, (self.y1 + self.y2) / 2)

    @property
    def corners(self) -> tuple[Point2D, ...]:
        return (
            Point2D(self.x1, self.y1),
            Point2D(self.x2, self.y1),
            Point2D(self.x2, self.y2),
            Point2D(self.x1, self.y2),
        )


@dataclass(frozen=True)
class ObservationConfidence:
    detector: float | None = None
    tracker: float | None = None
    geometry: float | None = None
    final: float | None = None
    # final = minimum available components (conservative evidence bottleneck).


@dataclass
class Detection:
    class_id: int
    class_name: str
    confidence: float
    bbox: BoundingBox
    track_id: int | None = None
    is_stable: bool = False
    duration_frames: int = 1
    reference_polygon: tuple[Point2D, ...] | None = None
    motion: MotionState = MotionState.UNKNOWN
    velocity_reference_frame: Point2D | None = None
    continuity_key: int | None = None
    identity_persistent: bool = False
    identity_ambiguous: bool = False
    is_context: bool = False
    track_status: str = "tentative"
    track_quality: float | None = None
    track_age_frames: int = 0
    frames_since_seen: int = 0

    @property
    def bbox_xyxy(self) -> tuple[float, float, float, float]:
        return self.bbox.x1, self.bbox.y1, self.bbox.x2, self.bbox.y2


@dataclass
class HandObservation:
    """Hand evidence with anatomical handedness after mirror correction.

    Known labels ``Left`` / ``Right`` mean the subject's anatomical left/right
    hand, regardless of input mirroring; None means unknown. ``mirrored_input``
    is metadata only. Consumers must not perform another handedness swap.
    """
    hand_id: str | None
    handedness: str | None
    confidence: float | None
    landmarks: list[Point2D]
    palm_center: Point2D
    identity_persistent: bool = False
    handedness_confidence: float | None = None
    reference_landmarks: list[Point2D] | None = None
    reference_palm_center: Point2D | None = None
    continuity_key: int | None = None
    identity_ambiguous: bool = False
    mirrored_input: bool = False
    # Provenance only; handedness has already been corrected by the producer.


@dataclass
class PoseObservation:
    landmarks: list[Point2D]
    confidence: float | None = None
    reference_landmarks: list[Point2D] | None = None


@dataclass
class HandObjectAssociation:
    hand_index: int
    detection_index: int
    coordinate_frame: CoordinateFrame
    palm_distance: float
    minimum_landmark_distance: float
    landmarks_inside: int
    hand_box_iou: float
    hand_contained: bool
    near: bool
    contact_candidate: bool
    ambiguous: bool
    confidence: ObservationConfidence
    distance_trend: DistanceTrend = DistanceTrend.UNKNOWN
    previously_near: bool = False
    hand_key: int | None = None
    object_key: int | None = None
    is_context: bool = False
    distance_rate_per_s: float | None = None
    leaving_transition: bool = False
    distance_units: str = "image_diagonal_units"


@dataclass
class InteractionPrimitive:
    interaction_type: InteractionType
    hand_id: str | None
    object_id: str | None
    object_class: str
    confidence: ObservationConfidence
    duration_frames: int = 1
    detection_index: int = 0
    hand_index: int | None = None
    coordinate_frame: CoordinateFrame = CoordinateFrame.IMAGE_DIAGONAL
    identity_reliable: bool = False
    observed: bool = True
    frames_since_seen: int = 0
    hand_continuity_key: int | None = None
    object_continuity_key: int | None = None
    ambiguous: bool = False
    event_timestamp_s: float | None = None


class ReferenceSource(str, Enum):
    NONE = "none"
    STATIC_MANUAL = "static_manual"
    ARUCO = "aruco"
    LIVE_MARKERS = "live_markers"


@dataclass
class ReferenceFrameInfo:
    valid: bool = False
    reference_id: str | None = None
    image_to_reference_matrix: tuple[tuple[float, ...], ...] | None = None
    axes_pixels: tuple[Point2D, Point2D, Point2D] | None = None
    source: ReferenceSource = ReferenceSource.NONE
    verified_this_frame: bool = False
    verified_timestamp_s: float | None = None


@dataclass
class OptimizationObservations:
    frame_id: int
    timestamp_s: float
    source_id: str
    image_width: int = 0
    image_height: int = 0
    detections: list[Detection] = field(default_factory=list)
    hands: list[HandObservation] = field(default_factory=list)
    poses: list[PoseObservation] = field(default_factory=list)
    associations: list[HandObjectAssociation] = field(default_factory=list)
    interactions: list[InteractionPrimitive] = field(default_factory=list)
    coordinate_frame_valid: bool = False
    association_coordinate_frame: CoordinateFrame = CoordinateFrame.IMAGE_DIAGONAL
    reference_frame: ReferenceFrameInfo = field(default_factory=ReferenceFrameInfo)
    processing_time_ms: float = 0.0
    stage_timings_ms: dict[str, float] = field(default_factory=dict)
    warnings: list[Diagnostic] = field(default_factory=list)
    notices: list[Diagnostic] = field(default_factory=list)
    status: ModuleStatus = ModuleStatus.OK
    reliable_for_temporal_reasoning: bool = False
    session_id: str = "default"

    def to_dict(self) -> dict:
        """Includes reliability and provenance; optional confidence serializes as null."""
        from dataclasses import asdict

        return asdict(self)

    @property
    def timestamp(self) -> float:
        """Compatibility spelling; retains the shared monotonic seconds convention."""
        return self.timestamp_s


# Compatibility name only. This is Module 03's detailed payload, never Module 01's output.
PerceptionFrameResult = OptimizationObservations
