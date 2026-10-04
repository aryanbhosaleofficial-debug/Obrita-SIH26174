"""Module 01 -> Module 02 packet. Source pixels remain authoritative."""

from dataclasses import dataclass, field, replace

import numpy as np

from shared.diagnostics import Diagnostic
from shared.enums.module_status import ModuleStatus
from shared.schemas.frame_packet import FramePacket
from shared.schemas.observations import (
    BoundingBox,
    Detection,
    HandObservation,
    Point2D,
    PoseObservation,
)


@dataclass
class PreparedFrame:
    image: np.ndarray
    scale_x: float
    scale_y: float
    source: FramePacket | None = None
    status: ModuleStatus = ModuleStatus.OK
    warnings: list[Diagnostic] = field(default_factory=list)
    notices: list[Diagnostic] = field(default_factory=list)
    stage_timings_ms: dict[str, float] = field(default_factory=dict)
    missing_frames: int = 0
    reset_required: bool = False
    accepted: bool = True

    def source_point(self, point: Point2D) -> Point2D:
        return Point2D(point.x / self.scale_x, point.y / self.scale_y)

    def source_detection(self, detection: Detection) -> Detection:
        b = detection.bbox
        return replace(
            detection,
            bbox=BoundingBox(
                b.x1 / self.scale_x,
                b.y1 / self.scale_y,
                b.x2 / self.scale_x,
                b.y2 / self.scale_y,
            ),
        )

    def source_hand(self, hand: HandObservation) -> HandObservation:
        return replace(
            hand,
            landmarks=[self.source_point(p) for p in hand.landmarks],
            palm_center=self.source_point(hand.palm_center),
        )

    def source_pose(self, pose: PoseObservation) -> PoseObservation:
        return replace(pose, landmarks=[self.source_point(p) for p in pose.landmarks])
