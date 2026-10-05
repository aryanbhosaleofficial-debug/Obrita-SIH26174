"""Module 06 stage: PreparedFrame -> PoseFrame (body + hand landmarks).

Runs beside Module 02 on the same PreparedFrame; it never consumes or modifies
ObjectFrame or OptimizationOutputPacket. "No person" / "no hands" is a normal
NO_DETECTION result. A per-frame backend failure yields an ERROR PoseFrame for
that frame only; the stream keeps going.
"""

from __future__ import annotations

import logging
import math
from threading import RLock
from time import perf_counter

from pose_tracking.backends import (
    LandmarkBackend,
    MediaPipeLandmarkBackend,
    RawLandmark,
)
from pose_tracking.config import PoseTrackingConfig
from pose_tracking.contracts import LEFT, RIGHT, UNKNOWN, Landmark, PoseFrame
from pose_tracking.landmarks import BODY_LANDMARK_NAMES, HAND_LANDMARK_NAMES
from pose_tracking.smoothing import HandCandidate, LandmarkStabilizer

from shared.diagnostics import Diagnostic, WarningCode
from shared.enums.module_status import ModuleStatus
from shared.schemas.prepared_frame import PreparedFrame

LOGGER = logging.getLogger("pose_tracking.tracker")
_MODEL_SIDES = {"left": LEFT, "right": RIGHT}


class PoseHandTracker:
    """One ordered source/session per instance; ``reset()`` before switching source."""

    def __init__(
        self, config: PoseTrackingConfig, backend: LandmarkBackend | None = None
    ):
        self.config = config.validate()
        self.backend = (
            backend if backend is not None else MediaPipeLandmarkBackend(self.config)
        )
        self.stabilizer = LandmarkStabilizer(self.config)
        self._lock = RLock()
        self._initialized = False
        self._failure_reported = False
        self._clear_cursor()

    # Lifecycle -----------------------------------------------------------------
    def initialize(self) -> None:
        """Load models once. Raises shared InitializationError on setup failure."""
        with self._lock:
            if not self._initialized:
                self.backend.initialize()
                self._initialized = True

    def close(self) -> None:
        with self._lock:
            try:
                self.backend.close()
            finally:
                self._initialized = False

    def reset(self) -> None:
        """Clear smoothing/hold state and the model's internal tracking state."""
        with self._lock:
            was_initialized = self._initialized
            self.stabilizer.reset()
            self._clear_cursor()
            self._failure_reported = False
            self.close()
            if was_initialized:
                self.initialize()

    def __enter__(self):
        self.initialize()
        return self

    def __exit__(self, *exc):
        self.close()

    def _clear_cursor(self) -> None:
        self._identity: tuple[str, str] | None = None
        self._last_frame_id: int | None = None
        self._last_timestamp_s: float | None = None

    # Processing ----------------------------------------------------------------
    def process(self, prepared: PreparedFrame) -> PoseFrame:
        if not isinstance(prepared, PreparedFrame):
            raise TypeError("PoseHandTracker consumes shared.schemas.PreparedFrame")
        source = prepared.source
        if source is None:
            raise ValueError("PreparedFrame must retain its source FramePacket")
        with self._lock:
            started = perf_counter()
            base = {
                "frame_id": source.frame_id,
                "timestamp_s": source.timestamp_s,
                "source_id": source.source_id,
                "session_id": source.session_id,
                "image_width": source.width,
                "image_height": source.height,
            }

            def empty(status, *warnings):
                return PoseFrame(
                    **base,
                    status=status,
                    warnings=tuple(warnings),
                    processing_time_ms=(perf_counter() - started) * 1000,
                )

            # Rejected by Module 01: publish an empty packet, touch no state.
            if not prepared.accepted or prepared.status in (
                ModuleStatus.INVALID_INPUT,
                ModuleStatus.ERROR,
            ):
                return empty(
                    ModuleStatus.INVALID_INPUT,
                    *(
                        prepared.warnings
                        or [
                            Diagnostic(
                                WarningCode.UPSTREAM_FAILURE,
                                {"stage": "prepared_frame"},
                            )
                        ]
                    ),
                )
            identity = (source.source_id, source.session_id)
            if self._identity is not None and identity != self._identity:
                return empty(
                    ModuleStatus.INVALID_INPUT,
                    Diagnostic(
                        WarningCode.SOURCE_CHANGED, {"action": "reset before switching"}
                    ),
                )
            if (
                self._last_frame_id is not None
                and source.frame_id <= self._last_frame_id
            ) or (
                self._last_timestamp_s is not None
                and source.timestamp_s <= self._last_timestamp_s
            ):
                return empty(
                    ModuleStatus.INVALID_INPUT,
                    Diagnostic(WarningCode.NON_MONOTONIC_FRAME),
                )
            self._identity = identity
            self._last_frame_id = source.frame_id
            self._last_timestamp_s = source.timestamp_s

            # Module 01 diagnostics (missing frames, history reset, degraded source)
            # are carried through unchanged so the cause stays machine-readable.
            warnings: list[Diagnostic] = list(prepared.warnings)
            if prepared.reset_required:
                self.stabilizer.reset()
                if WarningCode.TEMPORAL_HISTORY_RESET not in {w.code for w in warnings}:
                    warnings.append(Diagnostic(WarningCode.TEMPORAL_HISTORY_RESET))
            if not self._initialized:
                self.initialize()
            try:
                raw = self.backend.detect(prepared.image, source.timestamp_s)
            except Exception as exc:  # noqa: BLE001 -- one bad frame must not stop the stream
                if not self._failure_reported:
                    LOGGER.warning("landmark inference failed: %s", exc)
                    self._failure_reported = True
                return empty(
                    ModuleStatus.ERROR,
                    *warnings,
                    Diagnostic(WarningCode.POSE_TRACKER_FAILURE, {"reason": str(exc)}),
                )
            self._failure_reported = False
            if self.config.body_enabled and not raw.body_available:
                warnings.append(
                    Diagnostic(WarningCode.POSE_TRACKER_FAILURE, {"stage": "init"})
                )
            if self.config.hands_enabled and not raw.hands_available:
                warnings.append(
                    Diagnostic(WarningCode.HAND_TRACKER_FAILURE, {"stage": "init"})
                )

            width, height = source.width, source.height
            body = None
            if self.config.body_enabled and raw.body is not None:
                body = _to_landmarks(raw.body, BODY_LANDMARK_NAMES, width, height)
                if body is None:
                    warnings.append(
                        Diagnostic(WarningCode.INVALID_OBSERVATION, {"what": "body"})
                    )
            candidates = []
            if self.config.hands_enabled:
                for raw_hand in raw.hands[: self.config.max_hands]:
                    points = _to_landmarks(
                        raw_hand.landmarks, HAND_LANDMARK_NAMES, width, height
                    )
                    if points is None:
                        warnings.append(
                            Diagnostic(
                                WarningCode.INVALID_OBSERVATION, {"what": "hand"}
                            )
                        )
                        continue
                    candidates.append(
                        HandCandidate(
                            self._side(raw_hand.label),
                            points,
                            raw_hand.score,
                            raw_hand.label,
                        )
                    )
            candidates = _resolve_duplicate_sides(candidates)

            body_out, body_since, hands = self.stabilizer.update(
                source.frame_id,
                source.timestamp_s,
                math.hypot(width, height),
                body,
                candidates,
            )
            body_detected = body is not None
            observed_any = body_detected or bool(candidates)
            if warnings:
                status = ModuleStatus.DEGRADED
            else:
                status = ModuleStatus.OK if observed_any else ModuleStatus.NO_DETECTION
            visibilities = [p.visibility for p in body_out if p.visibility is not None]
            return PoseFrame(
                **base,
                body_landmarks=body_out,
                hands=hands,
                body_detected=body_detected,
                body_frames_since_seen=body_since,
                status=status,
                warnings=tuple(warnings),
                processing_time_ms=(perf_counter() - started) * 1000,
                body_score=(
                    sum(visibilities) / len(visibilities)
                    if body_detected and visibilities
                    else None
                ),
            )

    def _side(self, label: str | None) -> str:
        side = _MODEL_SIDES.get((label or "").lower(), UNKNOWN)
        if side != UNKNOWN and self.config.effective_swap_handedness:
            side = RIGHT if side == LEFT else LEFT
        return side


def _to_landmarks(raw: tuple[RawLandmark, ...], names, width: int, height: int):
    """Normalized model output -> source-pixel Landmarks; None if any value is invalid.

    Normalized coordinates are resolution independent, so the mapping uses the
    ORIGINAL source size even if Module 01 resized the inference image.
    """
    if len(raw) != len(names):
        return None
    try:
        return tuple(
            Landmark(i, name, p.x * width, p.y * height, p.z, p.visibility, p.presence)
            for i, (p, name) in enumerate(zip(raw, names, strict=True))
        )
    except (ValueError, TypeError):
        return None


def _resolve_duplicate_sides(candidates: list[HandCandidate]) -> list[HandCandidate]:
    """Two hands with the same label: the higher score keeps it, the other is UNKNOWN."""
    output: list[HandCandidate] = []
    for side in (LEFT, RIGHT):
        same = [c for c in candidates if c.handedness == side]
        if not same:
            continue
        best = max(same, key=lambda c: c.handedness_score or 0.0)
        output.append(best)
        output.extend(
            HandCandidate(UNKNOWN, c.landmarks, c.handedness_score, c.model_handedness)
            for c in same
            if c is not best
        )
    output.extend(c for c in candidates if c.handedness == UNKNOWN)
    return output
