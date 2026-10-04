"""
ObjectFrame — tracked object detections for one frame.

Originating module: Module 02 — YOLO
Consuming modules:  Module 03 (ROIs, interaction, rack reference),
                    Module 04 and Module 05 via OptimizationOutputPacket.object_frame

Coordinate system:
    All boxes are (x1, y1, x2, y2) pixels in the ORIGINAL source frame
    (letterbox padding and scaling already removed).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal, Optional

from shared.enums.module_status import ModuleStatus

BBoxXYXY = tuple[float, float, float, float]

TrackStatus = Literal["tentative", "confirmed", "lost", "reacquired"]
# tentative  - newly created, not yet confirmed
# confirmed  - tracked consistently
# lost       - not matched in recent frames (box is the last known / predicted box)
# reacquired - matched again after being lost, same track_id


@dataclass
class DetectedObject:
    class_name: str
    # Class name as configured in configs/classes.yaml.

    class_id: int
    # Model class index.

    confidence: float
    # Detection confidence in [0.0, 1.0].

    bbox_xyxy: BBoxXYXY
    # Original-frame pixels.

    track_id: Optional[int] = None
    # Persistent id from the tracker; None if tracking is disabled / not yet assigned.

    track_status: TrackStatus = "tentative"
    track_quality: Optional[float] = None
    # Tracker quality score in [0.0, 1.0]; definition documented in 02_yolo/README.md.

    track_age_frames: int = 0
    frames_since_seen: int = 0

    is_stable: bool = False
    # True only after multi-frame confirmation (02_yolo/stability/).


@dataclass
class ReferenceAnchor:
    anchor_role: str
    # Reference role from configs/classes.yaml, e.g. "rack" or "payload".

    track_id: Optional[int]
    bbox_xyxy: BBoxXYXY
    # Original-frame pixels.

    confidence: float
    # [0.0, 1.0]

    keypoints_px: list[tuple[float, float]] = field(default_factory=list)
    # Optional anchor keypoints (e.g. corners) in original-frame pixels.


@dataclass
class ObjectFrame:
    # Required ---------------------------------------------------------------
    frame_id: int
    timestamp_s: float
    # Copied unchanged from the source FramePacket.

    image_width: int
    image_height: int
    # Size of the original source frame the coordinates refer to.

    # Optional ---------------------------------------------------------------
    detections: list[DetectedObject] = field(default_factory=list)
    reference_anchors: list[ReferenceAnchor] = field(default_factory=list)
    # Empty when no anchor is visible. Never fabricated.

    status: ModuleStatus = ModuleStatus.OK
