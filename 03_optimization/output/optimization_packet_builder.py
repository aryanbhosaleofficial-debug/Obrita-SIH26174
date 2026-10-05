"""One canonical packet builder shared by temporal-only and spatial entry points."""

from dataclasses import replace

from shared.enums.module_status import ModuleStatus
from shared.schemas.object_frame import ObjectFrame
from shared.schemas.observations import OptimizationObservations
from shared.schemas.optimization_packet import OptimizationOutputPacket
from shared.schemas.spatial_feature_packet import Landmark, SpatialFeaturePacket


def build_optimization_packet(
    objects: ObjectFrame, observations: OptimizationObservations
) -> OptimizationOutputPacket:
    result = observations
    result.reliable_for_temporal_reasoning = result.status in (
        ModuleStatus.OK,
        ModuleStatus.NO_DETECTION,
    ) and any(d.is_stable for d in result.detections)
    spatial = SpatialFeaturePacket(
        result.frame_id,
        result.timestamp_s,
        hands=result.hands,
        status=result.status,
        reference_frame=result.reference_frame,
    )
    if result.poses:
        pose = result.poses[0]
        spatial.pose_landmarks = [Landmark(p.x, p.y) for p in pose.landmarks]
        spatial.rack_relative_pose = [
            (p.x, p.y, None) for p in (pose.reference_landmarks or [])
        ]
    reasons = []
    if not result.reliable_for_temporal_reasoning:
        reasons = [w.code.value for w in result.warnings]
        if result.status in (
            ModuleStatus.ERROR,
            ModuleStatus.INVALID_INPUT,
            ModuleStatus.DEGRADED,
        ):
            reasons.append(f"upstream_or_processing_{result.status.value}")
        if not any(d.is_stable for d in result.detections):
            reasons.append("no_current_confirmed_detection")
    return OptimizationOutputPacket(
        result.frame_id,
        result.timestamp_s,
        object_frame=replace(
            objects,
            detections=result.detections,
            reference_anchors=list(objects.reference_anchors),
            warnings=list(objects.warnings),
            notices=list(objects.notices),
            stage_timings_ms=dict(objects.stage_timings_ms),
        ),
        spatial=spatial,
        observations=result,
        interactions=result.interactions,
        quality_ok=result.reliable_for_temporal_reasoning,
        quality_reasons=reasons,
        status=result.status,
        source_id=result.source_id,
        session_id=result.session_id,
        reliable_for_temporal_reasoning=result.reliable_for_temporal_reasoning,
        warnings=result.warnings,
        notices=result.notices,
        stage_timings_ms=result.stage_timings_ms,
    )
