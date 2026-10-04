from copy import deepcopy

import numpy as np
import pytest

from perception import FramePacket, PerceptionConfig, PerceptionPipeline
from perception.config import DetectorConfig, HandTrackerConfig, ReferenceFrameConfig
from perception.mocks import demo_backends


@pytest.fixture
def config():
    return PerceptionConfig(
        detector=DetectorConfig(backend="mock"),
        hand_tracker=HandTrackerConfig(backend="mock"),
        reference_frame=ReferenceFrameConfig(
            enabled=True, corners_normalized=[[0, 0], [1, 0], [1, 1], [0, 1]]
        ),
    )


@pytest.fixture
def packet():
    def make(frame_id=0, timestamp=None, image=None, source="test"):
        image = np.zeros((240, 320, 3), np.uint8) if image is None else image
        return FramePacket(
            frame_id,
            frame_id / 30 if timestamp is None else timestamp,
            image,
            image.shape[1],
            image.shape[0],
            source_id=source,
        )

    return make


@pytest.fixture
def scene():
    detector, hands = demo_backends()
    return deepcopy(detector.frames[0]), deepcopy(hands.frames[0])


@pytest.fixture
def pipeline(config):
    detector, hands = demo_backends()
    instance = PerceptionPipeline(config, detector=detector, hand_tracker=hands)
    yield instance
    instance.close()
