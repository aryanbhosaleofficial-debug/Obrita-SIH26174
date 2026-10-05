"""Module 03/06 producers agree on anatomical sides, without inference assets."""
from types import SimpleNamespace

import numpy as np
import pytest

from optimization.hands.hand_tracker import MediaPipeHandTracker
from perception.core import FrameProcessor
from pose_tracking.backends import RawHand, RawLandmark, RawResult
from pose_tracking.config import load_config
from pose_tracking.sync import to_hand_observations
from pose_tracking.tracker import PoseHandTracker
from shared.config import HandTrackerConfig
from shared.schemas.frame_packet import FramePacket
from shared.schemas.observations import HandObservation


@pytest.mark.parametrize("mirrored", [False, True])
@pytest.mark.parametrize("anatomical", ["Left", "Right"])
def test_producers_publish_same_anatomical_side_and_mirror_metadata(mirrored, anatomical):
    raw_label = ("Right" if anatomical == "Left" else "Left") if mirrored else anatomical
    points = tuple(RawLandmark(.2 + .005 * (i % 5), .4 + .005 * (i // 5), 0.) for i in range(21))

    class HandTask:
        def detect_for_video(self, image, timestamp_ms):
            return SimpleNamespace(hand_landmarks=[points],
                                   handedness=[[SimpleNamespace(category_name=raw_label, score=.95)]])

        def close(self):
            pass

    class TrackingBackend:
        def initialize(self):
            pass

        def detect(self, image_bgr, timestamp_s):
            return RawResult(hands=(RawHand(points, raw_label, .95),))

        def close(self):
            pass

    image = np.zeros((100, 200, 3), np.uint8)
    module03 = MediaPipeHandTracker(HandTrackerConfig(mirrored=mirrored))
    module03._landmarker = HandTask()
    module03._mp = SimpleNamespace(Image=lambda **kwargs: kwargs, ImageFormat=SimpleNamespace(SRGB="rgb"))
    with PoseHandTracker(load_config(input_mirrored=mirrored), TrackingBackend()) as module06:
        prepared = FrameProcessor().process(FramePacket(0, 0., image, 200, 100))
        observations06 = to_hand_observations(module06.process(prepared))
        observations03 = module03.track(image, 0.)
    module03.close()
    assert observations03[0].handedness == observations06[0].handedness == anatomical
    assert observations03[0].mirrored_input is mirrored
    assert observations06[0].mirrored_input is mirrored
    assert observations03[0].handedness_confidence == observations06[0].handedness_confidence == .95


def test_shared_hand_contract_documents_producer_correction():
    assert "anatomical handedness after mirror correction" in HandObservation.__doc__
    assert "metadata only" in HandObservation.__doc__
    assert "must not perform another handedness swap" in HandObservation.__doc__
