"""Import-safe public facade; shared contracts have one authoritative definition."""

from shared.schemas.frame_packet import FramePacket
from shared.schemas.perception_frame_result import (
    BoundingBox,
    CoordinateFrame,
    Detection,
    DistanceTrend,
    HandObjectAssociation,
    HandObservation,
    InteractionPrimitive,
    InteractionType,
    MotionState,
    ObservationConfidence,
    PerceptionFrameResult,
    Point2D,
    PoseObservation,
    ReferenceFrameInfo,
)

__all__ = [
    "BoundingBox",
    "CoordinateFrame",
    "Detection",
    "DistanceTrend",
    "FramePacket",
    "HandObjectAssociation",
    "HandObservation",
    "InteractionPrimitive",
    "InteractionType",
    "MotionState",
    "ObservationConfidence",
    "PerceptionFrameResult",
    "Point2D",
    "PoseObservation",
    "ReferenceFrameInfo",
]
