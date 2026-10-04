"""
BoundaryOutputPacket — boundary / contact evidence for the target object.

Originating module: Module 04 — Boundary Detection
Consuming module:   Module 05 — Perception Fusion

This packet carries EVIDENCE only. It never states whether a procedure step
was correct; that is the Procedure FSM's job.

Coordinate system:
    Contour points: pixels in the ORIGINAL source frame.
    Orientation:    degrees relative to the rack reference x-axis (not camera "up").
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from shared.enums.boundary_state import BoundaryState
from shared.enums.module_status import ModuleStatus


@dataclass
class BoundaryOutputPacket:
    # Required ---------------------------------------------------------------
    frame_id: int
    timestamp_s: float
    # Copied unchanged from the input OptimizationOutputPacket.

    # Optional ---------------------------------------------------------------
    target_track_id: Optional[int] = None
    # Operator track_id (same meaning as in OptimizationOutputPacket).

    target_object_track_id: Optional[int] = None
    # Object whose boundary was analysed.

    boundary_state: BoundaryState = BoundaryState.UNKNOWN
    state_confirmed: bool = False
    confirmed_frames: int = 0

    contour_px: list[tuple[float, float]] = field(default_factory=list)
    # Resampled contour, original-frame pixels.

    chain_code: list[int] = field(default_factory=list)
    # Normalized Freeman chain code (values 0-7).

    differential_chain_code: list[int] = field(default_factory=list)
    chain_histogram: list[float] = field(default_factory=list)
    # 8 bins, normalized to sum to 1 when non-empty.

    area_px: Optional[float] = None
    perimeter_px: Optional[float] = None
    centroid_px: Optional[tuple[float, float]] = None
    orientation_deg_rack: Optional[float] = None
    # None when the rack reference is invalid.

    hand_contact: bool = False
    contact_confidence: float = 0.0

    crosscheck_agrees: Optional[bool] = None
    # Agreement with Module 03 motion/interaction; None if not evaluated.

    confidence: float = 0.0
    quality_ok: bool = False
    quality_reasons: list[str] = field(default_factory=list)
    status: ModuleStatus = ModuleStatus.OK
