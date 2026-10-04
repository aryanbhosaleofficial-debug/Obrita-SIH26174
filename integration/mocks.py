"""Deterministic scripted backends for integration without models or camera."""

from __future__ import annotations

from copy import deepcopy
from typing import Generic, TypeVar

import numpy as np

from shared.schemas.observations import BoundingBox, Detection, HandObservation, Point2D

T = TypeVar("T")


class _ScriptedBackend(Generic[T]):
    """Repeat the final frame; an empty script returns no observations."""

    def __init__(self, frames: list[list[T]] | None = None):
        self.frames = deepcopy(frames or [])
        self.index = 0
        self.closed = False

    def initialize(self) -> None:
        self.index = 0
        self.closed = False

    def _next(self) -> list[T]:
        if self.closed:
            raise RuntimeError("mock backend is closed")
        result = (
            deepcopy(self.frames[min(self.index, len(self.frames) - 1)])
            if self.frames
            else []
        )
        self.index += 1
        return result

    def close(self) -> None:
        self.closed = True


class MockDetector(_ScriptedBackend[Detection]):
    def detect(self, image: np.ndarray) -> list[Detection]:
        return self._next()


class MockHandTracker(_ScriptedBackend[HandObservation]):
    def track(
        self, image: np.ndarray, timestamp_s: float | None = None
    ) -> list[HandObservation]:
        return self._next()


def demo_backends() -> tuple[MockDetector, MockHandTracker]:
    """Synthetic 320x240 scene. These scores are test fixtures, not measurements."""
    detection = Detection(
        0, "sample_container", 0.9, BoundingBox(120, 80, 200, 160), track_id=7
    )
    hand = HandObservation(
        "demo_hand",
        None,
        0.85,
        [Point2D(130, 110), Point2D(160, 120), Point2D(170, 130)],
        Point2D(150, 120),
        True,
    )
    return MockDetector([[detection]]), MockHandTracker([[hand]])
