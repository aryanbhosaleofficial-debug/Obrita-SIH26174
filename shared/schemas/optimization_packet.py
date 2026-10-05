"""
OptimizationOutputPacket — spatial + temporal perception features for one frame.

Originating module: Module 03 — Optimization Sequence (assembled by Teammate 4)
Consuming modules:  Module 04 — Boundary Detection, Module 05 — Perception Fusion

`object_frame` contains detached, filtered CURRENT observations enriched by
Module 03. `stable_detections` also includes explicitly unobserved short-gap
evidence. Consumers must not use held boxes as fresh detections. The immutable
temporal window contains metadata only, never image arrays or upstream packets.

Units:
    Motion values are in rack-relative units (see RackReference) per second,
    computed from timestamp_s differences. They are not metric unless calibrated.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from shared.enums.module_status import ModuleStatus
from shared.schemas.object_frame import ObjectFrame
from shared.schemas.observations import BoundingBox
from shared.schemas.spatial_feature_packet import SpatialFeaturePacket


@dataclass(frozen=True)
class TemporalDetection:
    """One object's evidence at a window frame; bbox is the last observed box.

    confidence is an EMA of accepted observations, not a probability of presence.
    raw_confidence and tracker metadata describe the last actual observation.
    continuity_key is local to one optimizer run and restarts on explicit reset.
    """

    continuity_key: int
    class_id: int
    class_name: str
    bbox: BoundingBox
    track_id: int | None
    identity_persistent: bool
    identity_ambiguous: bool
    raw_confidence: float
    confidence: float
    confirmed: bool
    observed: bool
    consecutive_seen: int
    observed_frames: int
    frames_since_seen: int
    first_seen_frame_id: int
    first_seen_timestamp_s: float
    last_seen_frame_id: int
    last_seen_timestamp_s: float
    track_status: str
    track_quality: float | None
    track_age_frames: int


@dataclass(frozen=True)
class TemporalFrame:
    """All active tentative/confirmed states at one processed frame.

    Source/session/dimensions are inherited from the containing packet; the
    window is cleared when that context changes. Gaps are counted, not filled
    with invented observations. Status records upstream object-stage health.
    """

    frame_id: int
    timestamp_s: float
    detections: tuple[TemporalDetection, ...]
    missing_frames_before: int = 0
    status: ModuleStatus = ModuleStatus.OK


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
    # Same-frame current observations and spatial features; treat as read-only.

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
    stable_detections: tuple[TemporalDetection, ...] = ()
    temporal_window: tuple[TemporalFrame, ...] = ()
    raw_detection_count: int = 0
    filtered_detection_count: int = 0
    duplicate_detection_count: int = 0

    @property
    def stable_detection_count(self) -> int:
        return len(self.stable_detections)
