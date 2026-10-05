"""Model-free fixtures for Module 03's shared contracts."""

import pytest

from shared.schemas.object_frame import ObjectFrame
from shared.schemas.observations import BoundingBox, Detection


@pytest.fixture
def detection():
    def make(track_id=7, class_id=0, confidence=0.9, x=10, **kwargs):
        return Detection(
            class_id,
            f"class_{class_id}",
            confidence,
            BoundingBox(x, 10, x + 20, 30),
            track_id,
            **kwargs,
        )

    return make


@pytest.fixture
def object_frame():
    def make(frame_id=0, detections=(), **kwargs):
        return ObjectFrame(
            frame_id,
            kwargs.pop("timestamp_s", frame_id / 30),
            kwargs.pop("image_width", 320),
            kwargs.pop("image_height", 240),
            list(detections),
            **kwargs,
        )

    return make
