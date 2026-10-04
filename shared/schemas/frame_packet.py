"""
FramePacket — one captured frame plus its metadata.

Originating module: Module 01 — Perception Core
Consuming modules:  Module 02 (YOLO), Module 03 (pose/hands need the source image),
                    Module 04 (boundary ROI needs the source image)

The image is the ORIGINAL source frame. No module may modify it in place;
modules that need a resized / preprocessed version work on a copy.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional

from shared.enums.module_status import ModuleStatus


@dataclass
class FramePacket:
    # Required ---------------------------------------------------------------
    frame_id: int
    # Strictly increasing per source, assigned at capture time, never reused.

    timestamp_s: float
    # Monotonic capture time in seconds (time.monotonic based). Use for ordering
    # and time differences, not as wall-clock time.

    image: Any
    # numpy.ndarray, shape (height, width, 3), dtype uint8, channel order given by
    # `color_format`. Typed as Any so this schema does not force a numpy import.

    width: int
    height: int
    # Actual frame size in pixels (may differ from the size requested in camera.yaml).

    # Optional ---------------------------------------------------------------
    source_id: str = "camera_0"
    # Identifier of the camera / video source.

    color_format: str = "BGR"
    # OpenCV default channel order.

    wall_time_iso: Optional[str] = None
    # Human-readable capture time for logs only.

    dropped_frames_before: int = 0
    # Number of frames known to be dropped immediately before this one.

    status: ModuleStatus = ModuleStatus.OK
    metadata: dict[str, Any] = field(default_factory=dict)
    # Free-form debug metadata. Do not put contract fields here.
