"""Offline Module 03 optimization sequence pipeline.

The pipeline consumes Module 01/02 data and never performs object detection.
Pose and hands are optional MediaPipe adapters; all temporal, geometry and
gesture logic is dependency-light and deterministic for edge execution.
"""
from __future__ import annotations

from collections import deque
from math import hypot
from typing import Any, Iterable

try:
    from shared.enums.module_status import ModuleStatus
    from shared.enums.interaction_state import InteractionState
    from shared.schemas.optimization_packet import (OptimizationOutputPacket, MotionFeatures,
        InteractionCandidate, GestureResult)
except ImportError:  # pragma: no cover
    ModuleStatus = InteractionState = None  # type: ignore[assignment]


def _get(value, *names, default=None):
    if isinstance(value, dict):
        for name in names:
            if name in value:
                return value[name]
    else:
        for name in names:
            if hasattr(value, name):
                return getattr(value, name)
    return default


def _bbox(value):
    if value is None:
        return None
    box = _get(value, "bbox", "bbox_xyxy", default=None)
    if box is not None and len(box) >= 4:
        return [float(v) for v in box[:4]]
    return None


def _center(box):
    if not box or len(box) < 4:
        return (0.0, 0.0)
    return ((float(box[0]) + float(box[2])) / 2.0, (float(box[1]) + float(box[3])) / 2.0)


def _person(detections):
    people = [d for d in detections if str(_get(d, "class_name", "label", default="")).lower() in ("person", "human")]
    if not people:
        return None
    return max(people, key=lambda d: float(_get(d, "confidence", default=0.0)))


def _objects(detections):
    return [d for d in detections if str(_get(d, "class_name", "label", default="")).lower() not in ("person", "human")]


def _hand_point(hand):
    point = _get(hand, "center", default=None)
    if point is not None:
        if isinstance(point, (list, tuple)) and len(point) >= 2:
            return (float(point[0]), float(point[1]))
        if isinstance(point, dict):
            return (float(_get(point, "x", "x_px", default=0.0)), float(_get(point, "y", "y_px", default=0.0)))
    landmarks = _get(hand, "landmarks", default=[])
    if not landmarks:
        return None
    p = landmarks[0]
    if isinstance(p, dict):
        return (
            float(_get(p, "x", "x_px", default=0.0)),
            float(_get(p, "y", "y_px", default=0.0)),
        )
    if isinstance(p, (list, tuple)) and len(p) >= 2:
        return (float(p[0]), float(p[1]))
    return None


def _json_value(value):
    """Convert dataclass/model landmark values into JSON-safe primitives."""
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    if isinstance(value, (list, tuple)):
        return [_json_value(v) for v in value]
    if isinstance(value, dict):
        return {str(k): _json_value(v) for k, v in value.items()}
    if hasattr(value, "__dataclass_fields__"):
        return {name: _json_value(getattr(value, name)) for name in value.__dataclass_fields__}
    return str(value)


class OptimizationPipeline:
    def __init__(self, window_size=16, near_threshold=0.25, touch_threshold=0.05, pose_detector=None, hand_detector=None):
        self.window_size = int(window_size)
        self.near_threshold = float(near_threshold)
        self.touch_threshold = float(touch_threshold)
        self.history = deque(maxlen=self.window_size)
        self.pose_detector = pose_detector
        self.hand_detector = hand_detector
        self._last_points = {}
        self._last_timestamp = None
        self._state = "UNKNOWN"
        self._state_duration = 0
        self._last_person_track_id = None

    def _select_person(self, detections):
        person = _person(detections)
        if person is None:
            return None
        track_id = _get(person, "track_id", default=None)
        if self._last_person_track_id is not None and track_id is None:
            # Prefer the last valid track when multiple people are present but no track is assigned.
            for d in detections:
                t = _get(d, "track_id", default=None)
                if t == self._last_person_track_id:
                    return d
        if track_id is not None and track_id == self._last_person_track_id:
            return person
        return person

    def process(self, frame, frame_id, timestamp, detections, hands=None, pose_landmarks=None, rack=None):
        timestamp = float(timestamp)
        detections = list(detections or [])
        person = self._select_person(detections)
        if person is None:
            self._last_person_track_id = None
            return {"status": "NO_PERSON"}

        person_box = _bbox(person)
        self._last_person_track_id = _get(person, "track_id", default=self._last_person_track_id)

        if pose_landmarks is None and self.pose_detector is not None and frame is not None:
            try:
                pose_landmarks = self.pose_detector.detect(frame, person_box)
            except Exception:
                pose_landmarks = []
        pose_landmarks = list(pose_landmarks or [])

        if hands is None and self.hand_detector is not None and frame is not None:
            try:
                hands = self.hand_detector.detect(frame, person_box)
            except Exception:
                hands = []
        hands = [dict(h) if isinstance(h, dict) else h for h in (hands or [])]

        interactions = []
        for hand in hands:
            point = _hand_point(hand)
            if point is None:
                continue
            candidates = []
            for obj in _objects(detections):
                box = _bbox(obj)
                if not box:
                    continue
                x1, y1, x2, y2 = [float(v) for v in box[:4]]
                dx = max(float(x1) - point[0], 0.0, point[0] - float(x2))
                dy = max(float(y1) - point[1], 0.0, point[1] - float(y2))
                d = hypot(dx, dy) / max(hypot(float(x2) - float(x1), float(y2) - float(y1)), 1.0)
                candidates.append((d, obj))
            if candidates:
                d, obj = min(candidates, key=lambda x: x[0])
                touching = d <= self.touch_threshold
                near = d <= self.near_threshold
                state = "TOUCHING" if touching else ("NEAR" if near else "NONE")
                interactions.append({
                    "hand": _get(hand, "side", "handedness", default="unknown"),
                    "object_track_id": _get(obj, "track_id", default=None),
                    "distance_norm": d,
                    "state": state,
                    "near_object": near,
                    "contact_proxy": max(0.0, 1.0 - d / max(self.near_threshold, 1e-9)),
                })

        distances = [float(i["distance_norm"]) for i in interactions if isinstance(i.get("distance_norm"), (int, float))]
        self.history.append({"frame_id": int(frame_id), "timestamp": timestamp, "distances": distances})

        gesture, confidence = self._gesture()
        previous = self._state
        if gesture != self._state and (gesture != "UNKNOWN" or self._state == "UNKNOWN"):
            self._state, self._state_duration = gesture, 1
        else:
            self._state_duration += 1

        dt = timestamp - self._last_timestamp if self._last_timestamp is not None else 0.0
        motion = {}
        if hands:
            for hand in hands:
                key = _get(hand, "side", "handedness", default="unknown")
                point = _hand_point(hand)
                if point and key in self._last_points and dt > 0:
                    motion[key] = ((point[0] - self._last_points[key][0]) / dt, (point[1] - self._last_points[key][1]) / dt)
                if point:
                    self._last_points[key] = point
        self._last_timestamp = timestamp

        return _json_value({
            "module": "optimization_sequence",
            "frame_id": int(frame_id),
            "timestamp": timestamp,
            "status": "VALID" if pose_landmarks else "NO_POSE",
            "person": {
                "track_id": _get(person, "track_id", default=None),
                "bbox": list(person_box or []),
                "confidence": float(_get(person, "confidence", default=0.0)),
            },
            "pose": {"landmarks": pose_landmarks, "skeleton": [], "confidence": 1.0 if pose_landmarks else 0.0},
            "hands": hands,
            "motion": {"hand_velocity": motion},
            "hand_object_interaction": interactions,
            "gesture": {"name": gesture, "confidence": confidence},
            "temporal": {
                "window_size": self.window_size,
                "sequence_state": self._state,
                "previous_state": previous,
                "state_duration": self._state_duration,
            },
        })

    def _gesture(self):
        if len(self.history) < 2:
            return "UNKNOWN", 0.0
        values = [d for item in self.history for d in item["distances"]]
        if not values:
            return "UNKNOWN", 0.0
        latest = values[-1]
        first = values[0]
        if latest <= self.touch_threshold:
            return "TOUCH", 0.85
        if latest < first * 0.8:
            return "REACH", min(0.99, 0.6 + (first - latest))
        if latest > first * 1.2:
            return "RETRACT", 0.75
        return "UNKNOWN", 0.25


OptimizationSequencePipeline = OptimizationPipeline
