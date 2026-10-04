"""
OptimizationOutputPacket builder.

Implementation status:
    Scaffold only.

Input:
    SpatialFeaturePacket, motion, interaction, gesture and quality results

Output:
    OptimizationOutputPacket (shared/schemas/optimization_packet.py)

Owner:
    Module 03 — Optimization Sequence (Teammate 4: temporal section)
"""

from shared.schemas.optimization_packet import OptimizationOutputPacket, MotionFeatures
from shared.enums.module_status import ModuleStatus

def build_packet(frame_id, timestamp_s, target_track_id=None, object_frame=None, spatial=None, motion=None, interactions=None, gesture=None, quality_ok=False, quality_reasons=None, status=ModuleStatus.OK):
    return OptimizationOutputPacket(int(frame_id), float(timestamp_s), target_track_id, object_frame, spatial, motion or MotionFeatures(), list(interactions or []), gesture, bool(quality_ok), list(quality_reasons or []), status)
