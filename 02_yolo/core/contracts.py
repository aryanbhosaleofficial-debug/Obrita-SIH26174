"""Small Module 02 owned runtime contracts; standalone imports no SIH modules.

SIH supplies shared output constructors through adapters.sih. This keeps the
reviewed parser/filter and detector algorithm identical in both modes.
"""

import math
from dataclasses import dataclass, field, replace
from enum import Enum
from pathlib import Path
from typing import Any

import numpy as np


class ConfigurationError(ValueError):
    pass


class InitializationError(RuntimeError):
    pass


class ModuleStatus(str, Enum):
    OK = "ok"
    DEGRADED = "degraded"
    NO_DETECTION = "no_detection"
    INVALID_INPUT = "invalid_input"
    ERROR = "error"


class WarningCode(str, Enum):
    INVALID_FRAME = "invalid_frame"
    DETECTOR_FAILURE = "detector_failure"
    INVALID_OBSERVATION = "invalid_observation"
    CPU_FALLBACK = "cpu_fallback"


class NoticeCode(str, Enum):
    OBJECT_IDENTITY_UNAVAILABLE = "object_identity_unavailable"
    OBJECT_TRACKING_DISABLED = "object_tracking_disabled"
    DETECTOR_DISABLED = "detector_disabled"


@dataclass(frozen=True)
class Diagnostic:
    code: WarningCode | NoticeCode
    details: dict[str, Any] = field(default_factory=dict)


@dataclass
class DetectorConfig:
    backend: str = "ultralytics"
    model_path: Path | None = None
    confidence_threshold: float = 0.5
    iou_threshold: float = 0.45
    class_whitelist: list[int] | None = None
    device: str = "auto"
    cpu_fallback: bool = True
    tracking: bool = False
    tracker_path: Path | None = None
    classes_path: Path | None = None


@dataclass(frozen=True)
class Point2D:
    x: float
    y: float


@dataclass(frozen=True)
class BoundingBox:
    x1: float
    y1: float
    x2: float
    y2: float

    @property
    def center(self):
        return Point2D((self.x1 + self.x2) / 2, (self.y1 + self.y2) / 2)


@dataclass
class Detection:
    class_id: int
    class_name: str
    confidence: float
    bbox: BoundingBox
    track_id: int | None = None
    identity_persistent: bool = False

    @property
    def bbox_xyxy(self):
        return self.bbox.x1, self.bbox.y1, self.bbox.x2, self.bbox.y2


@dataclass
class SourceFrame:
    frame_id: int
    timestamp_s: float
    image: np.ndarray
    width: int
    height: int
    source_id: str = "standalone"
    session_id: str = "default"
    color_format: str = "BGR"


@dataclass
class InputFrame:
    image: np.ndarray
    scale_x: float
    scale_y: float
    source: SourceFrame | None
    status: ModuleStatus = ModuleStatus.OK
    warnings: list = field(default_factory=list)
    notices: list = field(default_factory=list)
    accepted: bool = True
    reset_required: bool = False

    def source_detection(self, detection):
        b = detection.bbox
        return replace(
            detection,
            bbox=type(b)(
                b.x1 / self.scale_x,
                b.y1 / self.scale_y,
                b.x2 / self.scale_x,
                b.y2 / self.scale_y,
            ),
        )


@dataclass
class DetectionFrame:
    """Standalone detection result, not the SIH wire schema."""

    frame_id: int
    timestamp_s: float
    image_width: int
    image_height: int
    detections: list[Detection] = field(default_factory=list)
    status: ModuleStatus = ModuleStatus.OK
    source_id: str = "standalone"
    session_id: str = "default"
    warnings: list[Diagnostic] = field(default_factory=list)
    notices: list[Diagnostic] = field(default_factory=list)
    stage_timings_ms: dict[str, float] = field(default_factory=dict)


# Output constructor slot selected by each adapter.
ResultFrame = DetectionFrame


def valid_score(score):
    return score is None or (
        isinstance(score, (float, int))
        and not isinstance(score, bool)
        and math.isfinite(score)
        and 0 <= score <= 1
    )
