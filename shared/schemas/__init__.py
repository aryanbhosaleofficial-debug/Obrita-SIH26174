"""
Shared packet schemas (inter-module contracts).

    FramePacket               Module 01 -> Modules 02, 03, 04
    ObjectFrame               Module 02 -> Module 03 (and via pass-through 04, 05)
    SpatialFeaturePacket      Module 03 spatial (Teammate 3) -> Module 03 temporal (Teammate 4)
    OptimizationOutputPacket  Module 03 -> Modules 04, 05
    BoundaryOutputPacket      Module 04 -> Module 05
    ActivityEvent             Module 05 -> Procedure FSM

Common conventions for every packet:
    frame_id     int    assigned once by Module 01, copied unchanged by every module
    timestamp_s  float  monotonic capture time in seconds from Module 01, copied unchanged
    status       ModuleStatus of the module that produced the packet
    Image coordinates are pixels in the ORIGINAL source frame (never letterboxed).
    Confidence values are floats in [0.0, 1.0].
"""

from shared.schemas.activity_event import ActivityEvent
from shared.schemas.boundary_packet import BoundaryOutputPacket
from shared.schemas.frame_packet import FramePacket
from shared.schemas.perception_frame_result import PerceptionFrameResult
from shared.schemas.object_frame import DetectedObject, ObjectFrame, ReferenceAnchor
from shared.schemas.optimization_packet import (
    GestureResult,
    InteractionCandidate,
    MotionFeatures,
    OptimizationOutputPacket,
)
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
    "FramePacket",
    "PerceptionFrameResult",
    "GestureResult",
    "HandLandmarks",
    "InteractionCandidate",
    "Landmark",
    "MotionFeatures",
    "ObjectFrame",
    "OptimizationOutputPacket",
    "RackReference",
    "ReferenceAnchor",
    "SpatialFeaturePacket",
]
