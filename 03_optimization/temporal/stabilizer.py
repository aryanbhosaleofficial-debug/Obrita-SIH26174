"""Bounded deterministic confirmation, conservative continuity, and rack motion."""

from __future__ import annotations

import math
from collections import deque
from dataclasses import dataclass, field, replace

from optimization.interaction.associations import box_iou

from shared.config import InteractionConfig, StabilizationConfig
from shared.geometry import isotropic_point
from shared.schemas.observations import (
    BoundingBox,
    CoordinateFrame,
    Detection,
    DistanceTrend,
    HandObjectAssociation,
    HandObservation,
    InteractionPrimitive,
    InteractionType,
    MotionState,
    Point2D,
)


@dataclass
class _Confirmation:
    hits: int = 0
    missing: int = 0
    confirmed: bool = False
    score: float | None = None

    def observe(self, score: float | None, minimum: int, alpha: float) -> None:
        self.hits += 1
        self.missing = 0
        self.confirmed = self.confirmed or self.hits >= minimum
        if score is not None:
            self.score = (
                score
                if self.score is None
                else alpha * score + (1 - alpha) * self.score
            )

    def miss(self) -> None:
        self.missing += 1
        if not self.confirmed:
            self.hits = 0


@dataclass
class _ObjectState:
    confirmation: _Confirmation
    class_id: int
    box: BoundingBox
    track_id: int | None
    reference_center: Point2D | None = None
    timestamp: float | None = None


@dataclass
class _HandState:
    palm: Point2D
    persistent_id: str | None
    missing: int = 0


@dataclass
class _PairHistory:
    distances: deque[tuple[float, float]] = field(
        default_factory=lambda: deque(maxlen=3)
    )
    near_state: bool = False
    near_hits: int = 0
    last_near_timestamp: float | None = None
    leaving_emitted: bool = False
    missing: int = 0


class PerceptionStabilizer:
    """Internal spatial continuity is not exposed as a persistent track ID.

    Confirmation needs consecutive observations initially; after confirmation a
    short dropout retains state. Only observations from the CURRENT frame are
    emitted. Missing counts expire state after max_missing_frames. Ambiguous
    one-to-many/many-to-one matches start new histories rather than guessing.
    """

    def __init__(self, config: StabilizationConfig, interaction: InteractionConfig):
        self.config = config
        self.interaction = interaction
        self.reset()

    def reset(self) -> None:
        self._objects: dict[int, _ObjectState] = {}
        self._hands: dict[int, _HandState] = {}
        self._interactions: dict[tuple, _Confirmation] = {}
        self._pairs: dict[tuple[int, int], _PairHistory] = {}
        self._next_object = getattr(self, "_next_object", 0)
        self._next_hand = getattr(self, "_next_hand", 0)
        self.object_keys: dict[int, int] = {}
        self.hand_keys: dict[int, int] = {}

    def reset_geometry(self) -> None:
        """Calibration changes invalidate distances/motion, not object presence."""
        self._interactions.clear()
        self._pairs.clear()
        for obj in self._objects.values():
            obj.reference_center = None
            obj.timestamp = None

    def age_missing(self, count: int) -> None:
        """Account for dropped/invalid source frames without allocating histories."""
        for _ in range(min(count, self.config.max_missing_frames + 1)):
            self.update_observations([], [], (1, 1), 0.0, False)
            self.update_interactions([])
            self.update_trends([], None)

    def update_observations(
        self,
        detections: list[Detection],
        hands: list[HandObservation],
        shape: tuple[int, int],
        timestamp: float,
        reference_valid: bool,
    ) -> None:
        self.object_keys = {}
        self.hand_keys = {}
        normalized_boxes = []
        choices: dict[int, list[int]] = {}
        for di, detection in enumerate(detections):
            b = detection.bbox
            height, width = shape
            box = BoundingBox(b.x1 / width, b.y1 / height, b.x2 / width, b.y2 / height)
            normalized_boxes.append(box)
            choices[di] = [
                key
                for key, state in self._objects.items()
                if state.class_id == detection.class_id
                and (
                    (
                        detection.track_id is not None
                        and state.track_id == detection.track_id
                    )
                    or (
                        detection.track_id is None
                        and state.track_id is None
                        and box_iou(box, state.box)
                        >= self.config.matching_iou_threshold
                    )
                )
            ]
        uses = {
            key: sum(key in candidates for candidates in choices.values())
            for key in self._objects
        }
        seen = set()
        for di, detection in enumerate(detections):
            candidates = choices[di]
            if len(candidates) == 1 and uses[candidates[0]] == 1:
                key = candidates[0]
                state = self._objects[key]
            else:
                key = self._next_object
                self._next_object += 1
                state = _ObjectState(
                    _Confirmation(),
                    detection.class_id,
                    normalized_boxes[di],
                    detection.track_id,
                )
                self._objects[key] = state
            seen.add(key)
            self.object_keys[di] = key
            detection.continuity_key = key
            detection.identity_persistent = detection.track_id is not None
            detection.identity_ambiguous = len(candidates) > 1 or any(
                uses.get(k, 0) > 1 for k in candidates
            )
            was_missing = state.confirmation.missing > 0
            state.confirmation.observe(
                detection.confidence,
                self.config.detection_min_frames,
                self.config.ema_alpha,
            )
            detection.is_stable = state.confirmation.confirmed
            detection.duration_frames = state.confirmation.hits
            # Keep raw detector confidence; EMA is used only on confirmed interactions.
            detection.motion = MotionState.UNKNOWN
            detection.velocity_reference_frame = None
            center = None
            if reference_valid and detection.reference_polygon:
                # Transform the box center via intersection of polygon diagonals,
                # not average corners (perspective homography is nonlinear).
                p0, p1, p2, p3 = detection.reference_polygon
                a = (p2.x - p0.x, p2.y - p0.y)
                diagonal_b = (p3.x - p1.x, p3.y - p1.y)
                cross = a[0] * diagonal_b[1] - a[1] * diagonal_b[0]
                if abs(cross) > 1e-12:
                    offset = (p1.x - p0.x, p1.y - p0.y)
                    t = (offset[0] * diagonal_b[1] - offset[1] * diagonal_b[0]) / cross
                    center = Point2D(p0.x + t * a[0], p0.y + t * a[1])
            if (
                detection.track_id is not None
                and detection.is_stable
                and center is not None
                and state.reference_center is not None
                and state.timestamp is not None
                and not was_missing
            ):
                dt = timestamp - state.timestamp
                if 0 < dt <= self.config.max_time_gap_s:
                    velocity = Point2D(
                        (center.x - state.reference_center.x) / dt,
                        (center.y - state.reference_center.y) / dt,
                    )
                    detection.velocity_reference_frame = velocity
                    detection.motion = (
                        MotionState.MOVING
                        if math.hypot(velocity.x, velocity.y)
                        > self.interaction.motion_speed_threshold
                        else MotionState.STATIONARY
                    )
            state.reference_center = center
            state.timestamp = timestamp if center is not None else None
            state.box = normalized_boxes[di]
        for key in list(self._objects):
            if key not in seen:
                self._objects[key].confirmation.miss()
                if (
                    self._objects[key].confirmation.missing
                    > self.config.max_missing_frames
                ):
                    del self._objects[key]

        palms = [isotropic_point(h.palm_center, shape) for h in hands]
        choices = {}
        for hi, hand in enumerate(hands):
            choices[hi] = [
                key
                for key, state in self._hands.items()
                if (
                    (hand.identity_persistent and state.persistent_id == hand.hand_id)
                    or (
                        not hand.identity_persistent
                        and state.persistent_id is None
                        and math.hypot(
                            palms[hi].x - state.palm.x, palms[hi].y - state.palm.y
                        )
                        <= self.config.hand_matching_distance
                    )
                )
            ]
        uses = {
            key: sum(key in candidates for candidates in choices.values())
            for key in self._hands
        }
        seen = set()
        for hi, hand in enumerate(hands):
            candidates = choices[hi]
            if len(candidates) == 1 and uses[candidates[0]] == 1:
                key = candidates[0]
            else:
                key = self._next_hand
                self._next_hand += 1
            self._hands[key] = _HandState(
                palms[hi], hand.hand_id if hand.identity_persistent else None
            )
            self.hand_keys[hi] = key
            hand.continuity_key = key
            hand.identity_ambiguous = len(candidates) > 1 or any(
                uses.get(k, 0) > 1 for k in candidates
            )
            seen.add(key)
        for key in list(self._hands):
            if key not in seen:
                self._hands[key].missing += 1
                if self._hands[key].missing > self.config.max_missing_frames:
                    del self._hands[key]

    def update_trends(
        self,
        associations: list[HandObjectAssociation],
        timestamp_s: float | None = None,
    ) -> None:
        seen = set()
        self._current_timestamp = timestamp_s
        for association in associations:
            key = (
                self.hand_keys[association.hand_index],
                self.object_keys[association.detection_index],
            )
            seen.add(key)
            history = self._pairs.setdefault(key, _PairHistory())
            history.missing = 0
            if timestamp_s is None:
                continue
            distance = association.minimum_landmark_distance
            thresholds = (
                self.interaction.rack_relative
                if association.coordinate_frame == CoordinateFrame.RACK_RELATIVE
                else self.interaction.image_diagonal
            )
            if history.distances:
                previous_time, previous_distance = history.distances[-1]
                elapsed = timestamp_s - previous_time
                if 0 < elapsed <= self.config.max_time_gap_s:
                    rate = (distance - previous_distance) / elapsed
                    association.distance_rate_per_s = rate
                    association.distance_trend = (
                        DistanceTrend.APPROACHING
                        if rate < -thresholds.trend_speed_threshold
                        else DistanceTrend.RETREATING
                        if rate > thresholds.trend_speed_threshold
                        else DistanceTrend.STEADY
                    )
            history.distances.append((timestamp_s, distance))
            association.previously_near = history.near_state
            if association.near:
                history.near_hits = history.near_hits + 1 if history.near_state else 1
                history.near_state = True
                history.last_near_timestamp = timestamp_s
                history.leaving_emitted = False
            elif history.near_state:
                # A single edge event; no permanent was-near latch. Missing frames
                # retain the previous state only within the timestamp window.
                history.near_state = False
                recent = (
                    history.last_near_timestamp is not None
                    and (timestamp_s - history.last_near_timestamp) * 1000
                    <= self.interaction.leaving_window_ms
                )
                association.leaving_transition = (
                    recent
                    and not history.leaving_emitted
                    and history.near_hits >= self.config.interaction_min_frames
                    and association.distance_trend == DistanceTrend.RETREATING
                )
                history.leaving_emitted = True
                history.near_hits = 0
        for key in list(self._pairs):
            if key not in seen:
                self._pairs[key].missing += 1
                if self._pairs[key].missing > self.config.max_missing_frames:
                    del self._pairs[key]

    def update_interactions(
        self,
        candidates: list[InteractionPrimitive],
        detections: list[Detection] | None = None,
    ) -> list[InteractionPrimitive]:
        output = []
        seen = set()
        for candidate in candidates:
            if candidate.interaction_type == InteractionType.LEAVING:
                if (
                    detections is None
                    or detections[candidate.detection_index].is_stable
                ):
                    output.append(
                        replace(candidate, event_timestamp_s=self._current_timestamp)
                    )
                continue
            object_key = self.object_keys[candidate.detection_index]
            hand_key = (
                self.hand_keys[candidate.hand_index]
                if candidate.hand_index is not None
                else None
            )
            key = (
                candidate.interaction_type,
                hand_key,
                object_key,
                candidate.coordinate_frame,
            )
            seen.add(key)
            state = self._interactions.setdefault(key, _Confirmation())
            state.observe(
                candidate.confidence.final,
                self.config.interaction_min_frames,
                self.config.ema_alpha,
            )
            if state.confirmed and (
                detections is None or detections[candidate.detection_index].is_stable
            ):
                output.append(
                    replace(
                        candidate,
                        duration_frames=state.hits,
                        confidence=replace(
                            candidate.confidence,
                            final=(
                                min(candidate.confidence.final, state.score)
                                if candidate.confidence.final is not None
                                and state.score is not None
                                else None
                            ),
                        ),
                    )
                )
        for key in list(self._interactions):
            if key not in seen:
                self._interactions[key].miss()
                if self._interactions[key].missing > self.config.max_missing_frames:
                    del self._interactions[key]
        return output
