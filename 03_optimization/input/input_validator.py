"""Strict shared ObjectFrame validation. Rejection never mutates temporal state."""

import math
from numbers import Integral, Real

from shared.diagnostics import Diagnostic, NoticeCode, WarningCode
from shared.enums.module_status import ModuleStatus
from shared.schemas.object_frame import ObjectFrame, ReferenceAnchor
from shared.schemas.observations import BoundingBox, Detection


class OptimizationInputError(ValueError):
    """A programmer/packet contract error, not a healthy empty frame."""


def _integer(value, name, minimum=0):
    if isinstance(value, bool) or not isinstance(value, Integral) or value < minimum:
        raise OptimizationInputError(f"{name} must be an integer >= {minimum}")


def _number(value, name, low=0.0, high=float("inf")):
    if (
        isinstance(value, bool)
        or not isinstance(value, Real)
        or not math.isfinite(value)
        or not low <= value <= high
    ):
        raise OptimizationInputError(f"{name} must be finite in [{low}, {high}]")


def validate_object_frame(frame: ObjectFrame, max_detections: int = 256) -> None:
    if not isinstance(frame, ObjectFrame):
        raise TypeError("Module 03 requires shared.schemas.object_frame.ObjectFrame")
    _integer(frame.frame_id, "frame_id")
    _number(frame.timestamp_s, "timestamp_s")
    _integer(frame.image_width, "image_width", 1)
    _integer(frame.image_height, "image_height", 1)
    for name in ("source_id", "session_id"):
        value = getattr(frame, name)
        if not isinstance(value, str) or not value.strip():
            raise OptimizationInputError(f"{name} must be a nonempty string")
    if not isinstance(frame.status, ModuleStatus):
        raise OptimizationInputError("status must be ModuleStatus")
    for name, code_type in (("warnings", WarningCode), ("notices", NoticeCode)):
        entries = getattr(frame, name)
        if not isinstance(entries, list) or any(
            not isinstance(entry, Diagnostic)
            or not isinstance(entry.code, code_type)
            or not isinstance(entry.details, dict)
            for entry in entries
        ):
            raise OptimizationInputError(f"{name} must contain typed diagnostics")
    if not isinstance(frame.stage_timings_ms, dict):
        raise OptimizationInputError("stage_timings_ms must be a mapping")
    for name, value in frame.stage_timings_ms.items():
        if not isinstance(name, str) or not name:
            raise OptimizationInputError("timing names must be nonempty strings")
        _number(value, f"stage_timings_ms.{name}")
    if not isinstance(frame.reference_anchors, list):
        raise OptimizationInputError("reference_anchors must be a list")
    for anchor in frame.reference_anchors:
        if not isinstance(anchor, ReferenceAnchor):
            raise OptimizationInputError(
                "reference_anchors must contain ReferenceAnchor"
            )
        if not isinstance(anchor.anchor_role, str) or not anchor.anchor_role:
            raise OptimizationInputError("anchor_role must be nonempty")
        if anchor.track_id is not None:
            _integer(anchor.track_id, "anchor.track_id")
        _number(anchor.confidence, "anchor.confidence", high=1)
        if not isinstance(anchor.bbox_xyxy, tuple) or len(anchor.bbox_xyxy) != 4:
            raise OptimizationInputError("anchor.bbox_xyxy must be an XYXY tuple")
        x1, y1, x2, y2 = anchor.bbox_xyxy
        for value, maximum in zip(
            anchor.bbox_xyxy,
            (
                frame.image_width,
                frame.image_height,
                frame.image_width,
                frame.image_height,
            ),
        ):
            _number(value, "anchor.bbox_xyxy", high=maximum)
        if x2 <= x1 or y2 <= y1:
            raise OptimizationInputError("anchor bbox must have positive area")
        if not isinstance(anchor.keypoints_px, list):
            raise OptimizationInputError("anchor.keypoints_px must be a list")
        for point in anchor.keypoints_px:
            if not isinstance(point, tuple) or len(point) != 2:
                raise OptimizationInputError("anchor keypoint must be an XY tuple")
            _number(point[0], "anchor.keypoint.x", high=frame.image_width)
            _number(point[1], "anchor.keypoint.y", high=frame.image_height)
    if not isinstance(frame.detections, list):
        raise OptimizationInputError("detections must be a list")
    if len(frame.detections) > max_detections:
        raise OptimizationInputError("max_detections_per_frame exceeded")
    if frame.status == ModuleStatus.NO_DETECTION and frame.detections:
        raise OptimizationInputError("NO_DETECTION must contain no detections")
    tracks = {}
    for index, detection in enumerate(frame.detections):
        label = f"detections[{index}]"
        if not isinstance(detection, Detection):
            raise OptimizationInputError(f"{label} must be shared Detection")
        _integer(detection.class_id, f"{label}.class_id")
        if (
            not isinstance(detection.class_name, str)
            or not detection.class_name.strip()
        ):
            raise OptimizationInputError(f"{label}.class_name must be nonempty")
        _number(detection.confidence, f"{label}.confidence", high=1)
        if not isinstance(detection.bbox, BoundingBox):
            raise OptimizationInputError(f"{label}.bbox must be BoundingBox")
        b = detection.bbox
        for name, maximum in (
            ("x1", frame.image_width),
            ("x2", frame.image_width),
            ("y1", frame.image_height),
            ("y2", frame.image_height),
        ):
            _number(getattr(b, name), f"{label}.bbox.{name}", high=maximum)
        if b.x2 <= b.x1 or b.y2 <= b.y1:
            raise OptimizationInputError(f"{label}.bbox must have positive area")
        if detection.track_id is not None:
            _integer(detection.track_id, f"{label}.track_id")
            signature = (detection.class_id, detection.class_name, b)
            if detection.track_id in tracks and tracks[detection.track_id] != signature:
                raise OptimizationInputError("conflicting detections for one track_id")
            tracks[detection.track_id] = signature
        if not isinstance(
            detection.track_status, str
        ) or detection.track_status not in {
            "tentative",
            "confirmed",
            "lost",
            "reacquired",
        }:
            raise OptimizationInputError(f"{label}.track_status is invalid")
        for name in ("track_age_frames", "frames_since_seen"):
            _integer(getattr(detection, name), f"{label}.{name}")
        if detection.track_quality is not None:
            _number(detection.track_quality, f"{label}.track_quality", high=1)
