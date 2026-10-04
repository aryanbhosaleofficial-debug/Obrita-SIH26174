"""Import-safe public facade; shared contracts have one authoritative definition."""

from shared.diagnostics import Diagnostic, NoticeCode, WarningCode
from shared.schemas.frame_packet import FramePacket
from shared.schemas.object_frame import ObjectFrame
from shared.schemas.observations import (
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
    OptimizationObservations,
    PerceptionFrameResult,
    Point2D,
    PoseObservation,
    ReferenceFrameInfo,
    ReferenceSource,
)
from shared.schemas.optimization_packet import OptimizationOutputPacket
from shared.schemas.prepared_frame import PreparedFrame

__all__ = [
    "BoundingBox",
    "CoordinateFrame",
    "Detection",
    "Diagnostic",
    "DistanceTrend",
    "FramePacket",
    "HandObjectAssociation",
    "HandObservation",
    "InteractionPrimitive",
    "InteractionType",
    "MotionState",
    "NoticeCode",
    "ObjectFrame",
    "ObservationConfidence",
    "OptimizationObservations",
    "OptimizationOutputPacket",
    "PerceptionFrameResult",
    "Point2D",
    "PoseObservation",
    "PreparedFrame",
    "ReferenceFrameInfo",
    "ReferenceSource",
    "WarningCode",
]
