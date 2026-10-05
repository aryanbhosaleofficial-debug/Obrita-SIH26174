"""Partial task failures must not reuse a MediaPipe VIDEO timestamp."""
from types import SimpleNamespace

import numpy as np
import pytest

from pose_tracking.backends import MediaPipeLandmarkBackend


@pytest.mark.parametrize("failing_task", ["pose", "hands"])
def test_reserved_timestamp_survives_partial_inference_failure(config, failing_task):
    class Task:
        def __init__(self, name):
            self.name, self.timestamps = name, []

        def detect_for_video(self, image, timestamp_ms):
            assert not self.timestamps or timestamp_ms > self.timestamps[-1]
            self.timestamps.append(timestamp_ms)  # task accepts timestamp first
            if self.name == failing_task and len(self.timestamps) == 1:
                raise RuntimeError("task failed after accepting timestamp")
            return SimpleNamespace(pose_landmarks=[], hand_landmarks=[], handedness=[])

    backend = MediaPipeLandmarkBackend(config())
    backend._mp = SimpleNamespace(Image=lambda **kwargs: kwargs, ImageFormat=SimpleNamespace(SRGB="rgb"))
    backend._pose, backend._hands = Task("pose"), Task("hands")
    image = np.zeros((32, 32, 3), np.uint8)
    with pytest.raises(RuntimeError, match="after accepting timestamp"):
        backend.detect(image, 0.)
    assert backend._last_ms == 0
    backend.detect(image, .0001)
    backend.detect(image, .0002)
    assert backend._pose.timestamps == [0, 1, 2]
    assert backend._hands.timestamps == ([1, 2] if failing_task == "pose" else [0, 1, 2])
