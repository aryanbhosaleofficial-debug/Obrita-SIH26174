"""MediaPipe Tasks Hand Landmarker isolated behind a BGR pixel interface."""

from __future__ import annotations

from dataclasses import replace
from typing import Any, Protocol

import cv2
import numpy as np

from perception.config import HandTrackerConfig
from perception.contracts import HandObservation, Point2D
from perception.detector import InitializationError
from perception.utils import valid_point, valid_score


class HandTracker(Protocol):
    def initialize(self) -> None: ...
    def track(self, image: np.ndarray) -> list[HandObservation]: ...
    def close(self) -> None: ...


class NullHandTracker:
    def initialize(self) -> None:
        pass

    def track(self, image: np.ndarray) -> list[HandObservation]:
        return []

    def close(self) -> None:
        pass


def filter_hands(hands: list[HandObservation]) -> tuple[list[HandObservation], int]:
    output = []
    invalid = 0
    ids = set()
    for hand in hands:
        if (
            not valid_score(hand.confidence)
            or not valid_score(hand.handedness_confidence)
            or not valid_point(hand.palm_center)
            or not all(valid_point(p) for p in hand.landmarks)
            or (
                hand.hand_id is not None
                and (not isinstance(hand.hand_id, str) or not hand.hand_id)
            )
            or (hand.identity_persistent and hand.hand_id is None)
            or (hand.identity_persistent and hand.hand_id in ids)
        ):
            invalid += 1
            continue
        if hand.identity_persistent:
            ids.add(hand.hand_id)
        output.append(replace(hand, landmarks=list(hand.landmarks)))
    return output, invalid


class MediaPipeHandTracker:
    """Supported Tasks API, synchronous IMAGE mode; no hidden live-stream callback.

    Tasks exposes handedness scores but no per-hand presence confidence in its
    result. confidence therefore stays None; handedness_confidence is separate.
    hand_N is a per-frame label, NOT a persistent identity. Temporal continuity
    is handled conservatively by geometry in the stabilizer.
    """

    def __init__(self, config: HandTrackerConfig):
        self.config = config
        self._landmarker: Any = None
        self._mp: Any = None

    def initialize(self) -> None:
        if self._landmarker is not None:
            return
        path = self.config.model_path
        if path is None or not path.is_file():
            raise InitializationError(
                f"hand model file not found: {path}; supply local hand_landmarker.task"
            )
        try:
            import mediapipe as mp
            from mediapipe.tasks import python
            from mediapipe.tasks.python import vision

            options = vision.HandLandmarkerOptions(
                base_options=python.BaseOptions(model_asset_path=str(path)),
                running_mode=vision.RunningMode.IMAGE,
                num_hands=self.config.max_hands,
                min_hand_detection_confidence=self.config.min_detection_confidence,
                min_hand_presence_confidence=self.config.min_presence_confidence,
                min_tracking_confidence=self.config.min_tracking_confidence,
            )
            self._landmarker = vision.HandLandmarker.create_from_options(options)
            self._mp = mp
        except Exception as exc:
            raise InitializationError(
                f"MediaPipe Tasks initialization failed: {exc}; install a supported Python/wheel combination"
            ) from exc

    def track(self, image: np.ndarray) -> list[HandObservation]:
        if self._landmarker is None:
            self.initialize()
        rgb = np.ascontiguousarray(cv2.cvtColor(image, cv2.COLOR_BGR2RGB))
        result = self._landmarker.detect(
            self._mp.Image(image_format=self._mp.ImageFormat.SRGB, data=rgb)
        )
        height, width = image.shape[:2]
        hands = []
        for index, raw in enumerate(result.hand_landmarks):
            if len(raw) != 21:
                continue
            landmarks = [Point2D(float(p.x * width), float(p.y * height)) for p in raw]
            palm = [landmarks[i] for i in (0, 5, 9, 13, 17)]
            categories = (
                result.handedness[index] if index < len(result.handedness) else []
            )
            category = max(categories, key=lambda c: c.score) if categories else None
            hands.append(
                HandObservation(
                    f"hand_{index}",
                    category.category_name if category else None,
                    None,
                    landmarks,
                    Point2D(
                        sum(p.x for p in palm) / len(palm),
                        sum(p.y for p in palm) / len(palm),
                    ),
                    handedness_confidence=float(category.score) if category else None,
                )
            )
        return hands

    def close(self) -> None:
        landmarker, self._landmarker = self._landmarker, None
        self._mp = None
        if landmarker is not None:
            landmarker.close()
