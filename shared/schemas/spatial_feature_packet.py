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
from typing import Literal, Optional

from shared.enums.module_status import ModuleStatus


@dataclass
class Landmark:
    x_px: float
    y_px: float
    z_rel: Optional[float] = None
    # Relative depth (see module docstring). None when unavailable.

    visibility: Optional[float] = None
    presence: Optional[float] = None
    # Model scores in [0.0, 1.0] when provided by the model.

    is_valid: bool = True
    is_interpolated: bool = False
    # True when filled in by missing-landmark handling, not observed.


@dataclass
class HandLandmarks:
    handedness: Literal["left", "right", "unknown"]
    handedness_score: Optional[float]
    landmarks: list[Landmark] = field(default_factory=list)
    # Ordered by the chosen hand model's landmark indices.


@dataclass
class RackReference:
    origin_px: tuple[float, float]
    # Rack/payload reference origin in original-frame pixels.

    x_axis: tuple[float, float]
    y_axis: tuple[float, float]
    # Unit vectors in the image plane defining rack-relative axes.

    scale_px_per_unit: Optional[float] = None
    # Pixels per rack-relative unit; None unless a scale reference is defined.

    source_anchor_track_id: Optional[int] = None
    is_valid: bool = False
    # False when no reliable anchor exists. Consumers must not substitute camera "up".


@dataclass
class SpatialFeaturePacket:
    # Required ---------------------------------------------------------------
    frame_id: int
    timestamp_s: float
    # Copied unchanged from FramePacket / ObjectFrame.

    # Optional ---------------------------------------------------------------
    target_track_id: Optional[int] = None
    # track_id (from ObjectFrame) of the operator whose pose is described.

    pose_landmarks: list[Landmark] = field(default_factory=list)
    hands: list[HandLandmarks] = field(default_factory=list)

    skeleton_bones: list[tuple[int, int]] = field(default_factory=list)
    # Landmark index pairs present in this frame (from skeleton/ connection tables).

    rack_reference: Optional[RackReference] = None
    rack_relative_pose: list[tuple[float, float, Optional[float]]] = field(default_factory=list)
    # Pose landmarks in rack-relative coordinates (x, y, z_rel); same order as pose_landmarks.

    status: ModuleStatus = ModuleStatus.OK
