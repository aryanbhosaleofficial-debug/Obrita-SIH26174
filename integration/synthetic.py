"""Synthetic pixels plus inference-only fakes. All five processing stages run."""
from copy import deepcopy
from dataclasses import replace

import cv2
import numpy as np

from integration.mocks import MockDetector, MockHandTracker
from shared.config import ReferenceFrameConfig
from shared.schemas.frame_packet import FramePacket
from shared.schemas.observations import BoundingBox, Detection, HandObservation, Point2D


def scene(count=36, session_id="synthetic"):
    packets, objects, hands = [], [], []
    for fid in range(count):
        present = fid < 30
        shift = max(0, min(fid - 14, 15)) * 2
        image = np.zeros((240, 320, 3), np.uint8)
        if present:
            cv2.rectangle(image, (110 + shift, 90), (170 + shift, 150), (255, 255, 255), -1)
        packets.append(FramePacket(fid, fid / 30, image, 320, 240,
                                   source_id="synthetic", session_id=session_id,
                                   metadata={"synthetic": True}))
        objects.append([Detection(0, "sample_container", 0.9,
                                  BoundingBox(90 + shift, 70, 190 + shift, 170),
                                  track_id=7, identity_persistent=True)] if present else [])
        hands.append([HandObservation("synthetic-hand", None, 0.9,
                                      [Point2D(110 + shift, 115), Point2D(120 + shift, 125), Point2D(115 + shift, 135)],
                                      Point2D(115 + shift, 125), True)] if present else [])
    return packets, MockDetector(objects), MockHandTracker(hands)


def configure(config):
    config = deepcopy(config)
    config.preprocessing = replace(config.preprocessing, max_width=None)
    config.detector = replace(config.detector, backend="mock", tracking=False, class_whitelist=None)
    config.hand_tracker = replace(config.hand_tracker, enabled=True, backend="mock")
    config.reference_frame = ReferenceFrameConfig(
        enabled=True, type="manual", reference_id="synthetic-rack",
        corners_normalized=[[0, 0], [1, 0], [1, 1], [0, 1]],
    )
    return config
