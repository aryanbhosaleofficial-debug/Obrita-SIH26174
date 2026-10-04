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
from typing import Optional

from shared.enums.interaction_state import InteractionState
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


@dataclass
class InteractionCandidate:
    hand: str
    # "left" / "right" / "unknown"

    object_track_id: int
    # track_id from ObjectFrame.

    state: InteractionState
    distance_norm: Optional[float] = None
    # Normalized hand-object distance (definition in 03_optimization/README.md).

    confidence: float = 0.0
    confirmed: bool = False
    # True after multi-frame confirmation.


@dataclass
class GestureResult:
    label: str
    # From the configured gesture label set; "unknown" when evidence is insufficient.

    confidence: float = 0.0
    window_start_frame_id: Optional[int] = None
    window_end_frame_id: Optional[int] = None
    confirmed: bool = False


@dataclass
class OptimizationOutputPacket:
    # Required ---------------------------------------------------------------
    frame_id: int
    timestamp_s: float

    # Optional ---------------------------------------------------------------
    target_track_id: Optional[int] = None
    # Operator track_id the features describe.

    object_frame: Optional[ObjectFrame] = None
    spatial: Optional[SpatialFeaturePacket] = None
    # Read-only pass-through of upstream packets for the same frame_id.

    motion: Optional[MotionFeatures] = None
    interactions: list[InteractionCandidate] = field(default_factory=list)
    gesture: Optional[GestureResult] = None

    quality_ok: bool = False
    quality_reasons: list[str] = field(default_factory=list)
    # Why the quality gate failed (empty when quality_ok is True).

    status: ModuleStatus = ModuleStatus.OK
