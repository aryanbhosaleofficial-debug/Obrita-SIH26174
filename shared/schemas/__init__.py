"""
Shared packet schemas (inter-module contracts).

    FramePacket               External capture -> Module 01; source retained for 03/04
    PreparedFrame             Module 01 -> Modules 02/03
    ObjectFrame               Module 02 -> Module 03 (and via pass-through 04, 05)
    SpatialFeaturePacket      Module 03 spatial (Teammate 3) -> Module 03 temporal (Teammate 4)
    OptimizationOutputPacket  Module 03 -> Modules 04, 05
    BoundaryOutputPacket      Module 04 -> Module 05
    ActivityEvent             Module 05 -> Procedure FSM

Common conventions for every packet:
    frame_id     int    assigned by the source within a session, copied unchanged
    timestamp_s  float  monotonic source seconds, copied unchanged
    status       ModuleStatus of the module that produced the packet
    Image coordinates are pixels in the ORIGINAL source frame (never letterboxed).
    Known confidence values are floats in [0.0, 1.0]; unavailable is None.
"""

from shared.schemas.activity_event import ActivityEvent
from shared.schemas.boundary_packet import BoundaryOutputPacket
from shared.schemas.frame_packet import FramePacket
from shared.schemas.object_frame import DetectedObject, ObjectFrame, ReferenceAnchor
from shared.schemas.observations import (
    Detection,
    HandObservation,
    InteractionPrimitive,
    OptimizationObservations,
    PerceptionFrameResult,
    ReferenceFrameInfo,
    ReferenceSource,
)
from shared.schemas.optimization_packet import (
    GestureResult,
    InteractionCandidate,
    MotionFeatures,
    OptimizationOutputPacket,
    TemporalDetection,
    TemporalFrame,
)
from shared.schemas.prepared_frame import PreparedFrame
from shared.schemas.spatial_feature_packet import (
    HandLandmarks,
    Landmark,
    RackReference,
    SpatialFeaturePacket,
)

__all__ = [
    "ActivityEvent",
    "BoundaryOutputPacket",
    "DetectedObject",
    "Detection",
    "FramePacket",
    "GestureResult",
    "HandLandmarks",
    "HandObservation",
    "InteractionCandidate",
    "InteractionPrimitive",
    "Landmark",
    "MotionFeatures",
    "ObjectFrame",
    "OptimizationObservations",
    "OptimizationOutputPacket",
    "PerceptionFrameResult",
    "PreparedFrame",
    "RackReference",
    "ReferenceAnchor",
    "ReferenceFrameInfo",
    "ReferenceSource",
    "SpatialFeaturePacket",
    "TemporalDetection",
    "TemporalFrame",
]
