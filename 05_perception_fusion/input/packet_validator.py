"""Validate shared packets before interpreting evidence; never repair bad input."""
import math
from numbers import Real
from shared.enums.module_status import ModuleStatus
from shared.enums.boundary_state import BoundaryState
from shared.schemas.optimization_packet import OptimizationOutputPacket
from shared.schemas.boundary_packet import BoundaryOutputPacket
from shared.schemas.object_frame import ObjectFrame
from shared.schemas.spatial_feature_packet import SpatialFeaturePacket
from shared.schemas.observations import InteractionType


def score(value, name, optional=False):
    if value is None and optional:
        return
    if isinstance(value, bool) or not isinstance(value, Real) or not math.isfinite(value) or not 0 <= value <= 1:
        raise ValueError(f"invalid {name} confidence: {value!r}")


def identity(packet):
    if type(packet.frame_id) is not int or packet.frame_id < 0 or isinstance(packet.timestamp_s, bool) or not isinstance(packet.timestamp_s, Real) or not math.isfinite(packet.timestamp_s) or packet.timestamp_s < 0:
        raise ValueError("invalid fusion frame_id/timestamp_s")
    if packet.target_track_id is not None and (type(packet.target_track_id) is not int or packet.target_track_id < 0):
        raise ValueError("invalid operator target_track_id")
    if not isinstance(packet.status, ModuleStatus) or packet.status in (ModuleStatus.ERROR, ModuleStatus.INVALID_INPUT):
        raise ValueError("fusion rejects upstream error/invalid_input status")


def validate_packets(optimization, boundary):
    if not isinstance(optimization, OptimizationOutputPacket):
        raise TypeError("fusion requires shared OptimizationOutputPacket")
    identity(optimization)
    if any(not isinstance(v, str) or not v for v in (optimization.source_id, optimization.session_id)):
        raise ValueError("fusion requires source/session identity")
    if type(optimization.quality_ok) is not bool:
        raise ValueError("quality_ok must be boolean")
    if optimization.object_frame is not None and not isinstance(optimization.object_frame, ObjectFrame):
        raise TypeError("fusion nested objects must be shared ObjectFrame")
    if optimization.spatial is not None and not isinstance(optimization.spatial, SpatialFeaturePacket):
        raise TypeError("fusion nested spatial must be shared SpatialFeaturePacket")
    for nested in (optimization.object_frame, optimization.spatial):
        if nested is not None and (nested.frame_id != optimization.frame_id or nested.timestamp_s != optimization.timestamp_s or nested.status in (ModuleStatus.ERROR, ModuleStatus.INVALID_INPUT)):
            raise ValueError("fusion nested packet identity/status mismatch")
    if optimization.object_frame:
        if (optimization.object_frame.source_id, optimization.object_frame.session_id) != (optimization.source_id, optimization.session_id):
            raise ValueError("fusion nested source/session mismatch")
        for detection in optimization.object_frame.detections:
            score(detection.confidence, "object")
            velocity = detection.velocity_reference_frame
            if velocity is not None and any(isinstance(v, bool) or not isinstance(v, Real) or not math.isfinite(v) for v in (velocity.x, velocity.y)):
                raise ValueError("invalid rack-relative velocity")
    if optimization.gesture:
        score(optimization.gesture.confidence, "gesture", optional=True)
    for item in optimization.interactions:
        if not isinstance(item.interaction_type, InteractionType) or type(item.detection_index) is not int or optimization.object_frame is None or not 0 <= item.detection_index < len(optimization.object_frame.detections):
            raise ValueError("interaction refers to an absent object or invalid state")
        detection = optimization.object_frame.detections[item.detection_index]
        if item.object_class != detection.class_name or (item.object_id is not None and item.object_id != str(detection.track_id)):
            raise ValueError("interaction target identity mismatch")
        for name in ("detector", "tracker", "geometry", "final"):
            score(getattr(item.confidence, name), "interaction", optional=True)
    if boundary is not None:
        if not isinstance(boundary, BoundaryOutputPacket):
            raise TypeError("fusion requires shared BoundaryOutputPacket")
        identity(boundary)
        if any(type(v) is not bool for v in (boundary.quality_ok, boundary.state_confirmed, boundary.hand_contact)):
            raise ValueError("boundary quality/contact/confirmation flags must be boolean")
        if not isinstance(boundary.boundary_state, BoundaryState):
            raise ValueError("invalid boundary state")
        if boundary.target_object_track_id is not None and (type(boundary.target_object_track_id) is not int or boundary.target_object_track_id < 0):
            raise ValueError("invalid boundary object track")
        score(boundary.confidence, "boundary")
        score(boundary.contact_confidence, "contact")
