"""Constant-size landmark smoothing and short-loss hold.

State is at most one body track plus one LEFT and one RIGHT hand track; no
history deque is kept, so memory does not grow with stream length. Held
outputs are explicitly marked (``observed=False`` / ``frames_since_seen>0``)
so downstream fusion never mistakes them for fresh observations.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from pose_tracking.config import PoseTrackingConfig
from pose_tracking.contracts import LEFT, RIGHT, UNKNOWN, HandPose, Landmark


@dataclass
class _Track:
    landmarks: tuple[Landmark, ...]
    last_seen_frame: int
    handedness_score: float | None = None
    model_handedness: str | None = None
    consecutive_frames: int = 1


@dataclass(frozen=True)
class HandCandidate:
    """A hand observed this frame, already mapped to source pixels and a side."""

    handedness: str
    landmarks: tuple[Landmark, ...]
    handedness_score: float | None = None
    model_handedness: str | None = None


def _centroid(landmarks: tuple[Landmark, ...]) -> tuple[float, float]:
    valid = [p for p in landmarks if p.is_valid]
    if not valid:
        return (0.0, 0.0)
    return (sum(p.x for p in valid) / len(valid), sum(p.y for p in valid) / len(valid))


def _blend(prev: tuple[Landmark, ...], new: tuple[Landmark, ...], alpha: float):
    beta = 1.0 - alpha
    return tuple(
        Landmark(
            n.index,
            n.name,
            alpha * n.x + beta * p.x,
            alpha * n.y + beta * p.y,
            alpha * n.z + beta * p.z,
            n.visibility,
            n.presence,
            n.is_valid,
        )
        if p.is_valid and n.is_valid else n
        for p, n in zip(prev, new, strict=True)
    )


class LandmarkStabilizer:
    def __init__(self, config: PoseTrackingConfig):
        self.alpha = config.smoothing_alpha
        self.max_hold_frames = config.max_hold_frames
        self.jump_reset_fraction = config.jump_reset_fraction
        self.max_time_gap_s = config.max_time_gap_s
        self.reset()

    def reset(self) -> None:
        self._body: _Track | None = None
        self._hands: dict[str, _Track] = {}
        self._last_timestamp_s: float | None = None

    @property
    def state_size(self) -> int:
        """Number of live tracks (bounded by 3)."""
        return (self._body is not None) + len(self._hands)

    @property
    def body_consecutive_frames(self) -> int:
        return self._body.consecutive_frames if self._body else 0

    def update(
        self,
        frame_id: int,
        timestamp_s: float,
        image_diagonal: float,
        body: tuple[Landmark, ...] | None,
        hands: list[HandCandidate],
    ) -> tuple[tuple[Landmark, ...], int, tuple[HandPose, ...]]:
        """Return (body_landmarks, body_frames_since_seen, hands) for this frame."""
        if (
            self._last_timestamp_s is not None
            and timestamp_s - self._last_timestamp_s > self.max_time_gap_s
        ):
            self.reset()
        self._last_timestamp_s = timestamp_s
        jump = self.jump_reset_fraction * image_diagonal

        # Body ---------------------------------------------------------------
        body_out: tuple[Landmark, ...] = ()
        body_since = 0
        if body is not None:
            self._body = self._observe(self._body, body, frame_id, jump)
            body_out = self._body.landmarks
        elif self._body is not None:
            self._body.consecutive_frames = 0
            since = frame_id - self._body.last_seen_frame
            if 0 < since <= self.max_hold_frames:
                body_out, body_since = self._body.landmarks, since
            else:
                self._body = None

        # Hands --------------------------------------------------------------
        # Compare against the previous frame, never tracks already updated by
        # another candidate in this frame. Labels can flicker between nearby
        # physical hands without exceeding the ordinary jump-reset threshold.
        previous_hands = dict(self._hands)
        output: dict[str, HandPose] = {}
        unknown: list[HandPose] = []
        for hand in hands:
            if hand.handedness == UNKNOWN:
                unknown.append(
                    HandPose(
                        UNKNOWN,
                        hand.landmarks,
                        hand.handedness_score,
                        hand.model_handedness,
                    )
                )
                continue
            previous = previous_hands.get(hand.handedness)
            opposite_side = RIGHT if hand.handedness == LEFT else LEFT
            opposite = previous_hands.get(opposite_side)
            if (previous is not None and opposite is not None
                    and 0 < frame_id - previous.last_seen_frame <= self.max_hold_frames + 1
                    and 0 < frame_id - opposite.last_seen_frame <= self.max_hold_frames + 1):
                center = _centroid(hand.landmarks)
                if math.dist(center, _centroid(opposite.landmarks)) < math.dist(center, _centroid(previous.landmarks)):
                    # Ambiguous physical association: publish the current
                    # observation without cross-hand EMA or a continuity claim.
                    previous = None
            track = self._observe(previous, hand.landmarks, frame_id, jump)
            track.handedness_score = hand.handedness_score
            track.model_handedness = hand.model_handedness
            self._hands[hand.handedness] = track
            output[hand.handedness] = HandPose(
                hand.handedness,
                track.landmarks,
                hand.handedness_score,
                hand.model_handedness,
                consecutive_frames=track.consecutive_frames,
            )
        for side in (LEFT, RIGHT):
            track = self._hands.get(side)
            if track is None or side in output:
                continue
            since = frame_id - track.last_seen_frame
            track.consecutive_frames = 0
            if 0 < since <= self.max_hold_frames:
                output[side] = HandPose(
                    side,
                    track.landmarks,
                    track.handedness_score,
                    track.model_handedness,
                    observed=False,
                    frames_since_seen=since,
                    consecutive_frames=0,
                )
            else:
                del self._hands[side]
        ordered = tuple(output[s] for s in (LEFT, RIGHT) if s in output) + tuple(
            unknown
        )
        return body_out, body_since, ordered

    def _observe(self, track: _Track | None, new, frame_id: int, jump: float) -> _Track:
        consecutive = (
            track.consecutive_frames + 1
            if track is not None and frame_id == track.last_seen_frame + 1 else 1
        )
        if (
            track is None
            or self.alpha >= 1.0
            or frame_id - track.last_seen_frame > self.max_hold_frames + 1
            or math.dist(_centroid(track.landmarks), _centroid(new)) > jump
        ):
            return _Track(new, frame_id, consecutive_frames=consecutive)
        return _Track(_blend(track.landmarks, new, self.alpha), frame_id,
                      consecutive_frames=consecutive)
