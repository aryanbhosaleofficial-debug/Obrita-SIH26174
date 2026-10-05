"""PoseFrame contract: body + hand landmarks for exactly one source frame.

Proposed shared packet. It lives in this module until the integration owner
promotes it to ``shared/schemas`` (see README "Schema change request"); the
field names follow the existing shared conventions:

    frame_id, timestamp_s, source_id, session_id
        Copied unchanged from the PreparedFrame's source FramePacket, so a
        PoseFrame and the ObjectFrame of the same frame share one FrameKey.
    x, y
        Pixels in the ORIGINAL source frame (never the resized/prepared image).
        Values may lie slightly outside the image: the pose model extrapolates
        occluded/out-of-view joints, which is reported via low ``visibility``.
    z
        Model-relative depth (pseudo-3D), unitless and NOT metric.
    visibility / presence
        Model scores in [0, 1]; None when the model does not provide them.
    status
        Shared ModuleStatus. "No person / no hands" is NO_DETECTION, not an error.

Coordinates are camera-image coordinates only. No camera "up"/"down" semantics
are derived here; rack-relative reasoning belongs to downstream modules.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from numbers import Integral, Real

from pose_tracking.landmarks import (
    BODY_INDEX,
    BODY_LANDMARK_NAMES,
    HAND_INDEX,
    HAND_LANDMARK_NAMES,
    PALM_INDICES,
)

from shared.diagnostics import Diagnostic
from shared.enums.module_status import ModuleStatus

LEFT = "LEFT"
RIGHT = "RIGHT"
UNKNOWN = "UNKNOWN"
HANDEDNESS_VALUES = (LEFT, RIGHT, UNKNOWN)


class PoseContractError(ValueError):
    """A PoseFrame/HandPose/Landmark violates the contract."""


def _score_ok(value) -> bool:
    return value is None or (
        isinstance(value, Real)
        and not isinstance(value, bool)
        and math.isfinite(value)
        and 0.0 <= value <= 1.0
    )


def _finite(value) -> bool:
    return (
        isinstance(value, Real) and not isinstance(value, bool) and math.isfinite(value)
    )


@dataclass(frozen=True)
class FrameKey:
    """Identity used to pair branch outputs that describe the same source frame."""

    source_id: str
    session_id: str
    frame_id: int
    timestamp_s: float


@dataclass(frozen=True)
class Landmark:
    index: int
    name: str
    x: float
    y: float
    z: float
    visibility: float | None = None
    presence: float | None = None

    def __post_init__(self):
        if not _finite(self.x) or not _finite(self.y) or not _finite(self.z):
            raise PoseContractError(f"landmark {self.name} coordinates must be finite")
        if not _score_ok(self.visibility) or not _score_ok(self.presence):
            raise PoseContractError(f"landmark {self.name} scores must be in [0, 1]")


def _check_landmarks(landmarks, names, what):
    if not isinstance(landmarks, tuple):
        raise PoseContractError(f"{what} landmarks must be a tuple")
    if len(landmarks) != len(names):
        raise PoseContractError(
            f"{what} requires {len(names)} landmarks, got {len(landmarks)}"
        )
    for i, (lm, name) in enumerate(zip(landmarks, names, strict=True)):
        if not isinstance(lm, Landmark) or lm.index != i or lm.name != name:
            raise PoseContractError(
                f"{what} landmark {i} must be Landmark({i}, {name!r})"
            )


@dataclass(frozen=True)
class HandPose:
    """One hand. ``observed`` False means a short-lived hold of the last observation."""

    handedness: str
    landmarks: tuple[Landmark, ...]
    handedness_score: float | None = None
    model_handedness: str | None = None
    # Raw model label before any mirror correction, kept for audit.
    observed: bool = True
    frames_since_seen: int = 0

    def __post_init__(self):
        if self.handedness not in HANDEDNESS_VALUES:
            raise PoseContractError(f"handedness must be one of {HANDEDNESS_VALUES}")
        _check_landmarks(self.landmarks, HAND_LANDMARK_NAMES, "hand")
        if not _score_ok(self.handedness_score):
            raise PoseContractError("handedness_score must be in [0, 1]")
        if (
            not isinstance(self.frames_since_seen, Integral)
            or isinstance(self.frames_since_seen, bool)
            or self.frames_since_seen < 0
            or (self.frames_since_seen == 0) != bool(self.observed)
        ):
            raise PoseContractError(
                "observed hands have frames_since_seen == 0, held hands > 0"
            )

    @property
    def wrist(self) -> Landmark:
        return self.landmarks[0]

    def landmark(self, name: str) -> Landmark:
        return self.landmarks[HAND_INDEX[name]]

    @property
    def palm_center(self) -> tuple[float, float]:
        pts = [self.landmarks[i] for i in PALM_INDICES]
        return (sum(p.x for p in pts) / len(pts), sum(p.y for p in pts) / len(pts))

    @property
    def bbox_xyxy(self) -> tuple[float, float, float, float]:
        xs = [p.x for p in self.landmarks]
        ys = [p.y for p in self.landmarks]
        return (min(xs), min(ys), max(xs), max(ys))


@dataclass(frozen=True)
class PoseFrame:
    frame_id: int
    timestamp_s: float
    body_landmarks: tuple[Landmark, ...] = ()
    hands: tuple[HandPose, ...] = ()
    body_detected: bool = False
    # True only when the body model observed a person in THIS frame.
    body_frames_since_seen: int = 0
    # 0 when observed; >0 when body_landmarks are a short hold of the last observation.
    source_id: str = "camera_0"
    session_id: str = "default"
    image_width: int = 0
    image_height: int = 0
    status: ModuleStatus = ModuleStatus.OK
    warnings: tuple[Diagnostic, ...] = ()
    processing_time_ms: float = 0.0
    body_score: float | None = field(default=None)
    # Mean landmark visibility of the observed body; None when not observed.

    def __post_init__(self):
        if (
            not isinstance(self.frame_id, Integral)
            or isinstance(self.frame_id, bool)
            or self.frame_id < 0
        ):
            raise PoseContractError("frame_id must be a nonnegative integer")
        if not _finite(self.timestamp_s):
            raise PoseContractError("timestamp_s must be finite")
        if not isinstance(self.source_id, str) or not self.source_id:
            raise PoseContractError("source_id must be a nonempty string")
        if not isinstance(self.session_id, str) or not self.session_id:
            raise PoseContractError("session_id must be a nonempty string")
        if not isinstance(self.status, ModuleStatus):
            raise PoseContractError("status must be a shared ModuleStatus")
        if self.body_landmarks:
            _check_landmarks(self.body_landmarks, BODY_LANDMARK_NAMES, "body")
        elif not isinstance(self.body_landmarks, tuple):
            raise PoseContractError("body landmarks must be a tuple")
        if (
            not isinstance(self.body_frames_since_seen, Integral)
            or self.body_frames_since_seen < 0
        ):
            raise PoseContractError("body_frames_since_seen must be nonnegative")
        if self.body_detected != (
            bool(self.body_landmarks) and self.body_frames_since_seen == 0
        ):
            raise PoseContractError(
                "body_detected must equal 'landmarks present and observed this frame'"
            )
        if not self.body_landmarks and self.body_frames_since_seen:
            raise PoseContractError("a held body requires landmarks")
        if not _score_ok(self.body_score) or (
            self.body_score is not None and not self.body_detected
        ):
            raise PoseContractError(
                "body_score is a [0, 1] score of an observed body only"
            )
        if not isinstance(self.hands, tuple) or not all(
            isinstance(h, HandPose) for h in self.hands
        ):
            raise PoseContractError("hands must be a tuple of HandPose")
        sides = [h.handedness for h in self.hands if h.handedness != UNKNOWN]
        if len(sides) != len(set(sides)):
            raise PoseContractError("at most one LEFT and one RIGHT hand per frame")

    @property
    def key(self) -> FrameKey:
        return FrameKey(
            self.source_id, self.session_id, self.frame_id, self.timestamp_s
        )

    @property
    def has_observation(self) -> bool:
        """Anything observed in THIS frame (held landmarks excluded)."""
        return self.body_detected or any(h.observed for h in self.hands)

    def hand(self, side: str) -> HandPose | None:
        """LEFT/RIGHT hand if present (observed or held), else None."""
        return next((h for h in self.hands if h.handedness == side), None)

    def body_landmark(self, name: str) -> Landmark | None:
        if not self.body_landmarks:
            return None
        return self.body_landmarks[BODY_INDEX[name]]
