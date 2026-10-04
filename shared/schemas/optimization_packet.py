"""
OptimizationOutputPacket — spatial + temporal perception features for one frame.

Originating module: Module 03 — Optimization Sequence (assembled by Teammate 4)
Consuming modules:  Module 04 — Boundary Detection, Module 05 — Perception Fusion

Pass-through fields (`object_frame`, `spatial`) are references to upstream
packets for the same frame_id. Consumers must treat them as read-only.

Units:
    Motion values are in rack-relative units (see RackReference) per second,
    computed from timestamp_s differences. They are not metric unless calibrated.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from shared.enums.module_status import ModuleStatus
from shared.schemas.object_frame import ObjectFrame
from shared.schemas.spatial_feature_packet import SpatialFeaturePacket


@dataclass
class MotionFeatures:
    joint_angles_deg: dict[str, float] = field(default_factory=dict)
    # Named joint angles in degrees.

    hand_velocity: dict[str, tuple[float, float]] = field(default_factory=dict)
    hand_acceleration: dict[str, tuple[float, float]] = field(default_factory=dict)
    # Keyed by "left" / "right"; rack-relative units per s and per s^2.

    motion_direction_deg: dict[str, float] = field(default_factory=dict)
    # Direction relative to rack x-axis, degrees.


from shared.diagnostics import Diagnostic
from shared.schemas.observations import InteractionPrimitive as InteractionCandidate
from shared.schemas.observations import OptimizationObservations


@dataclass
class GestureResult:
    label: str
    # From the configured gesture label set; "unknown" when evidence is insufficient.

    confidence: float | None = None
    window_start_frame_id: int | None = None
    window_end_frame_id: int | None = None
    confirmed: bool = False


@dataclass
class OptimizationOutputPacket:
    # Required ---------------------------------------------------------------
    frame_id: int
    timestamp_s: float

    # Optional ---------------------------------------------------------------
    target_track_id: int | None = None
    # Operator track_id the features describe.

    object_frame: ObjectFrame | None = None
    spatial: SpatialFeaturePacket | None = None
    # Read-only pass-through of upstream packets for the same frame_id.

    motion: MotionFeatures | None = None
    interactions: list[InteractionCandidate] = field(default_factory=list)
    gesture: GestureResult | None = None

    quality_ok: bool = False
    quality_reasons: list[str] = field(default_factory=list)
    # Why the quality gate failed (empty when quality_ok is True).

    status: ModuleStatus = ModuleStatus.OK
    observations: OptimizationObservations | None = None
    source_id: str = "camera_0"
    session_id: str = "default"
    reliable_for_temporal_reasoning: bool = False
    warnings: list[Diagnostic] = field(default_factory=list)
    notices: list[Diagnostic] = field(default_factory=list)
    stage_timings_ms: dict[str, float] = field(default_factory=dict)
