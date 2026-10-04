"""
SpatialFeaturePacket — pose, hands, skeleton and rack reference for one frame.

Originating module: Module 03 — spatial section (Teammate 3)
Consuming module:   Module 03 — temporal section (Teammate 4); passed through
                    to Modules 04 and 05 inside OptimizationOutputPacket.spatial

Coordinate systems:
    x_px, y_px  - pixels in the ORIGINAL source frame.
    z_rel       - RELATIVE depth from a monocular model (pseudo-3D). Unitless and
                  NOT metric. Do not interpret as distance in metres/millimetres
                  unless calibrated depth or stereo reconstruction is added.
    rack-relative coordinates - defined by RackReference below; units are
                  normalized / pixel-scaled, not metric unless calibrated.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from shared.enums.module_status import ModuleStatus


@dataclass
class Landmark:
    x_px: float
    y_px: float
    z_rel: float | None = None
    # Relative depth (see module docstring). None when unavailable.

    visibility: float | None = None
    presence: float | None = None
    # Model scores in [0.0, 1.0] when provided by the model.

    is_valid: bool = True
    is_interpolated: bool = False
    # True when filled in by missing-landmark handling, not observed.


from shared.schemas.observations import HandObservation as HandLandmarks
from shared.schemas.observations import ReferenceFrameInfo

# One reference metadata contract; legacy import remains an alias.
RackReference = ReferenceFrameInfo


@dataclass
class SpatialFeaturePacket:
    # Required ---------------------------------------------------------------
    frame_id: int
    timestamp_s: float
    # Copied unchanged from FramePacket / ObjectFrame.

    # Optional ---------------------------------------------------------------
    target_track_id: int | None = None
    # track_id (from ObjectFrame) of the operator whose pose is described.

    pose_landmarks: list[Landmark] = field(default_factory=list)
    hands: list[HandLandmarks] = field(default_factory=list)

    skeleton_bones: list[tuple[int, int]] = field(default_factory=list)
    # Landmark index pairs present in this frame (from skeleton/ connection tables).

    rack_relative_pose: list[tuple[float, float, float | None]] = field(
        default_factory=list
    )
    # Pose landmarks in rack-relative coordinates (x, y, z_rel); same order as pose_landmarks.

    status: ModuleStatus = ModuleStatus.OK
    reference_frame: ReferenceFrameInfo = field(default_factory=ReferenceFrameInfo)

    @property
    def rack_reference(self) -> ReferenceFrameInfo | None:
        """Compatibility view of the authoritative reference_frame field."""
        return self.reference_frame if self.reference_frame.valid else None
