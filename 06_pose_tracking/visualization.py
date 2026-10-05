"""Overlay rendering for PoseFrame / ObjectFrame. No inference, no state.

``draw_*`` functions draw in place on a BGR image whose pixel grid is the
ORIGINAL source frame (the coordinate system of both contracts).
``render_overlay`` copies the source image once and refuses to combine packets
from different frames, so boxes and skeletons always describe the same frame.
"""

from __future__ import annotations

from collections.abc import Iterable

import cv2
import numpy as np
from pose_tracking.contracts import LEFT, RIGHT, Landmark, PoseFrame
from pose_tracking.landmarks import (
    BODY_CONNECTIONS,
    FACE_CONNECTIONS,
    FINGERTIP_INDICES,
    HAND_CONNECTIONS,
)
from pose_tracking.sync import FrameSyncError, require_synchronized

from shared.schemas.object_frame import ObjectFrame

# BGR colours
BODY_EDGE = (255, 255, 255)
BODY_NODE = (0, 200, 255)
HELD = (140, 140, 140)
HAND_COLOURS = {LEFT: (80, 220, 80), RIGHT: (255, 140, 40)}
UNKNOWN_HAND = (200, 80, 220)
OBJECT_BOX = (0, 255, 0)
TEXT = (255, 255, 255)
FONT = cv2.FONT_HERSHEY_SIMPLEX
_FACE_EDGES = frozenset(FACE_CONNECTIONS)


def _pt(lm: Landmark) -> tuple[int, int]:
    return (round(lm.x), round(lm.y))


def _drawable(lm: Landmark, w: int, h: int, min_visibility: float) -> bool:
    visible = lm.visibility is None or lm.visibility >= min_visibility
    return visible and -w <= lm.x <= 2 * w and -h <= lm.y <= 2 * h


def draw_pose(
    image: np.ndarray, pose: PoseFrame, *, min_visibility: float = 0.5
) -> None:
    """Body skeleton: edges between visible joints, then joint nodes."""
    if not pose.body_landmarks:
        return
    h, w = image.shape[:2]
    held = not pose.body_detected
    edge, node = (HELD, HELD) if held else (BODY_EDGE, BODY_NODE)
    points = pose.body_landmarks
    ok = [_drawable(p, w, h, min_visibility) for p in points]
    for a, b in BODY_CONNECTIONS:
        if ok[a] and ok[b]:
            thickness = 1 if (a, b) in _FACE_EDGES else 2
            cv2.line(
                image, _pt(points[a]), _pt(points[b]), edge, thickness, cv2.LINE_AA
            )
    for i, p in enumerate(points):
        if ok[i]:
            cv2.circle(image, _pt(p), 2 if i <= 10 else 4, node, -1, cv2.LINE_AA)


def draw_hands(image: np.ndarray, pose: PoseFrame) -> None:
    """Hand skeletons (finger joints + palm) with a LEFT/RIGHT label at the wrist."""
    for hand in pose.hands:
        colour = (
            HELD
            if not hand.observed
            else HAND_COLOURS.get(hand.handedness, UNKNOWN_HAND)
        )
        pts = [_pt(p) for p in hand.landmarks]
        for a, b in HAND_CONNECTIONS:
            cv2.line(image, pts[a], pts[b], colour, 2, cv2.LINE_AA)
        for i, p in enumerate(pts):
            radius = 4 if i in FINGERTIP_INDICES else 3
            cv2.circle(image, p, radius, colour, -1, cv2.LINE_AA)
            cv2.circle(image, p, radius, (0, 0, 0), 1, cv2.LINE_AA)
        label = hand.handedness + ("" if hand.observed else " (held)")
        if hand.handedness_score is not None:
            label += f" {hand.handedness_score:.2f}"
        x, y = pts[0]
        _label(image, label, (x - 20, y + 22), colour)


def draw_objects(image: np.ndarray, objects: ObjectFrame) -> None:
    """YOLO boxes with class, confidence and track ID when available."""
    h, w = image.shape[:2]
    for d in objects.detections:
        x1, y1, x2, y2 = (round(v) for v in d.bbox_xyxy)
        x1, x2 = max(0, min(w - 1, x1)), max(0, min(w - 1, x2))
        y1, y2 = max(0, min(h - 1, y1)), max(0, min(h - 1, y2))
        cv2.rectangle(image, (x1, y1), (x2, y2), OBJECT_BOX, 2)
        label = f"{d.class_name} {d.confidence:.2f}"
        if d.track_id is not None:
            label += f" ID:{d.track_id}"
        _label(image, label, (x1, max(14, y1 - 6)), OBJECT_BOX)


def draw_status(image: np.ndarray, lines: Iterable[str]) -> None:
    for i, text in enumerate(lines):
        _label(image, text, (8, 22 + i * 22), TEXT)


def _label(image, text, origin, colour) -> None:
    cv2.putText(image, text, origin, FONT, 0.5, (0, 0, 0), 3, cv2.LINE_AA)
    cv2.putText(image, text, origin, FONT, 0.5, colour, 1, cv2.LINE_AA)


def status_lines(
    pose: PoseFrame, objects: ObjectFrame | None = None, fps: float | None = None
) -> list[str]:
    hands = (
        ",".join(h.handedness + ("" if h.observed else "*") for h in pose.hands)
        or "none"
    )
    body = "yes" if pose.body_detected else ("held" if pose.body_landmarks else "no")
    lines = [
        f"Frame:{pose.frame_id} Pose:{pose.status.value} Body:{body} Hands:{hands}",
    ]
    if objects is not None:
        lines.append(
            f"YOLO:{getattr(objects.status, 'value', objects.status)} "
            f"objects:{len(objects.detections)}"
        )
    if fps is not None:
        lines.append(
            f"FPS (measured): {fps:.1f}  pose {pose.processing_time_ms:.0f} ms"
        )
    return lines


def render_overlay(
    source_bgr: np.ndarray,
    pose: PoseFrame,
    objects: ObjectFrame | None = None,
    *,
    extra_lines: Iterable[str] = (),
    fps: float | None = None,
    min_visibility: float = 0.5,
) -> np.ndarray:
    """Detached display image: objects, body, hands, status text."""
    if (
        not isinstance(source_bgr, np.ndarray)
        or source_bgr.dtype != np.uint8
        or source_bgr.ndim != 3
        or source_bgr.shape[2] != 3
    ):
        raise ValueError("render_overlay requires a uint8 HxWx3 BGR source image")
    if pose.image_width and source_bgr.shape[:2] != (
        pose.image_height,
        pose.image_width,
    ):
        raise FrameSyncError("source image size differs from the PoseFrame coordinates")
    if objects is not None:
        require_synchronized(pose, objects)
    display = source_bgr.copy()
    if objects is not None:
        draw_objects(display, objects)
    draw_pose(display, pose, min_visibility=min_visibility)
    draw_hands(display, pose)
    draw_status(display, [*status_lines(pose, objects, fps), *extra_lines])
    return display
