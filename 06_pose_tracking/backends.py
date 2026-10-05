"""Landmark inference backends. MediaPipe is isolated here; the tracker sees raw tuples.

Uses the MediaPipe Tasks Pose Landmarker and Hand Landmarker in synchronous
VIDEO mode: one result per submitted frame, no callback queue, no backlog. The
models are loaded once from local files; nothing is downloaded at runtime.
"""

from __future__ import annotations

import logging
import math
from dataclasses import dataclass
from typing import Any, Protocol

import cv2
import numpy as np
from pose_tracking.config import PoseTrackingConfig
from pose_tracking.landmarks import BODY_LANDMARK_COUNT, HAND_LANDMARK_COUNT

from shared.errors import InitializationError

LOGGER = logging.getLogger("pose_tracking.backend")


@dataclass(frozen=True)
class RawLandmark:
    """Normalized [0, 1] image coordinates of the inference image (may exceed bounds)."""

    x: float
    y: float
    z: float
    visibility: float | None = None
    presence: float | None = None


@dataclass(frozen=True)
class RawHand:
    landmarks: tuple[RawLandmark, ...]
    label: str | None = None
    # Model label ("Left"/"Right") exactly as produced, before mirror correction.
    score: float | None = None


@dataclass(frozen=True)
class RawResult:
    body: tuple[RawLandmark, ...] | None = None
    hands: tuple[RawHand, ...] = ()
    body_available: bool = True
    hands_available: bool = True
    # False when that model is disabled or failed to initialize.


class LandmarkBackend(Protocol):
    def initialize(self) -> None: ...
    def detect(self, image_bgr: np.ndarray, timestamp_s: float) -> RawResult: ...
    def close(self) -> None: ...


class NullLandmarkBackend:
    """Detects nothing. Useful for wiring tests and model-free dry runs."""

    def initialize(self) -> None:
        pass

    def detect(self, image_bgr: np.ndarray, timestamp_s: float) -> RawResult:
        return RawResult()

    def close(self) -> None:
        pass


def _score(value) -> float | None:
    if value is None:
        return None
    value = float(value)
    return min(1.0, max(0.0, value)) if math.isfinite(value) else None


def _raw(points) -> tuple[RawLandmark, ...]:
    return tuple(
        RawLandmark(
            float(p.x),
            float(p.y),
            float(p.z) if p.z is not None else 0.0,
            _score(getattr(p, "visibility", None)),
            _score(getattr(p, "presence", None)),
        )
        for p in points
    )


class MediaPipeLandmarkBackend:
    """Pose + hands on one RGB conversion per frame.

    If exactly one of the two enabled models fails to initialize, the other
    keeps running and RawResult reports the missing one as unavailable. If no
    enabled model can initialize, InitializationError is raised.
    """

    def __init__(self, config: PoseTrackingConfig):
        self.config = config.validate()
        self._mp: Any = None
        self._pose: Any = None
        self._hands: Any = None
        self._epoch_s: float | None = None
        self._last_ms = -1
        self.init_errors: dict[str, str] = {}

    @property
    def initialized(self) -> bool:
        return self._pose is not None or self._hands is not None

    def initialize(self) -> None:
        if self.initialized:
            return
        try:
            import mediapipe as mp
            from mediapipe.tasks import python as mp_python
            from mediapipe.tasks.python import vision
        except Exception as exc:
            raise InitializationError(f"MediaPipe is not importable: {exc}") from exc
        self._mp = mp
        cfg = self.config
        self.init_errors = {}
        if cfg.body_enabled:
            try:
                self._pose = vision.PoseLandmarker.create_from_options(
                    vision.PoseLandmarkerOptions(
                        base_options=mp_python.BaseOptions(
                            model_asset_path=_model_path(cfg.pose_model_path, "pose")
                        ),
                        running_mode=vision.RunningMode.VIDEO,
                        num_poses=1,
                        min_pose_detection_confidence=cfg.min_pose_detection_confidence,
                        min_pose_presence_confidence=cfg.min_pose_presence_confidence,
                        min_tracking_confidence=cfg.min_tracking_confidence,
                        output_segmentation_masks=False,
                    )
                )
            except Exception as exc:  # noqa: BLE001 -- reported; hands may still run
                self.init_errors["body"] = str(exc)
                LOGGER.error("pose landmarker unavailable: %s", exc)
        if cfg.hands_enabled:
            try:
                self._hands = vision.HandLandmarker.create_from_options(
                    vision.HandLandmarkerOptions(
                        base_options=mp_python.BaseOptions(
                            model_asset_path=_model_path(cfg.hand_model_path, "hand")
                        ),
                        running_mode=vision.RunningMode.VIDEO,
                        num_hands=cfg.max_hands,
                        min_hand_detection_confidence=cfg.min_hand_detection_confidence,
                        min_hand_presence_confidence=cfg.min_hand_presence_confidence,
                        min_tracking_confidence=cfg.min_tracking_confidence,
                    )
                )
            except Exception as exc:  # noqa: BLE001 -- reported; body may still run
                self.init_errors["hands"] = str(exc)
                LOGGER.error("hand landmarker unavailable: %s", exc)
        if not self.initialized:
            self._mp = None
            raise InitializationError(
                "no landmark model could be initialized: "
                + "; ".join(f"{k}: {v}" for k, v in self.init_errors.items())
            )

    def detect(self, image_bgr: np.ndarray, timestamp_s: float) -> RawResult:
        if not self.initialized:
            self.initialize()
        if not math.isfinite(timestamp_s):
            raise ValueError("timestamp_s must be finite")
        if self._epoch_s is None:
            self._epoch_s = timestamp_s
        # VIDEO mode requires strictly increasing integer milliseconds. Two frames
        # inside one millisecond are nudged forward; this only affects MediaPipe's
        # internal tracking clock, never the published PoseFrame timestamp.
        timestamp_ms = max(
            round((timestamp_s - self._epoch_s) * 1000), self._last_ms + 1
        )
        rgb = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2RGB)
        image = self._mp.Image(image_format=self._mp.ImageFormat.SRGB, data=rgb)
        # Reserve the VIDEO timestamp before either task sees it. A task can
        # accept T then raise, or pose can accept T before hands fails. Retrying
        # within the same millisecond must still submit a strictly newer value.
        self._last_ms = timestamp_ms
        body = None
        if self._pose is not None:
            result = self._pose.detect_for_video(image, timestamp_ms)
            if (
                result.pose_landmarks
                and len(result.pose_landmarks[0]) == BODY_LANDMARK_COUNT
            ):
                body = _raw(result.pose_landmarks[0])
        hands: list[RawHand] = []
        if self._hands is not None:
            result = self._hands.detect_for_video(image, timestamp_ms)
            for index, points in enumerate(result.hand_landmarks):
                if len(points) != HAND_LANDMARK_COUNT:
                    continue
                categories = (
                    result.handedness[index] if index < len(result.handedness) else []
                )
                best = max(categories, key=lambda c: c.score) if categories else None
                hands.append(
                    RawHand(
                        _raw(points),
                        best.category_name if best else None,
                        _score(best.score) if best else None,
                    )
                )
        return RawResult(
            body,
            tuple(hands),
            body_available=self._pose is not None,
            hands_available=self._hands is not None,
        )

    def close(self) -> None:
        pose, hands = self._pose, self._hands
        self._pose = self._hands = self._mp = None
        self._epoch_s = None
        self._last_ms = -1
        for landmarker in (pose, hands):
            if landmarker is not None:
                try:
                    landmarker.close()
                except Exception as exc:  # noqa: BLE001 -- close must release the other one too
                    LOGGER.warning("landmarker close failed: %s", exc)


def _model_path(path, what: str) -> str:
    if path is None or not path.is_file():
        raise InitializationError(
            f"{what} model file not found: {path}. Place the official MediaPipe "
            f"{what} landmarker .task bundle there (see 06_pose_tracking/models/README.md)."
        )
    return str(path)
