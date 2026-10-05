"""The actual Module 04 receiver consumes temporal and spatial Module 03 packets."""

from dataclasses import replace

import numpy as np
import pytest
from boundary.input.contract_validator import (
    BoundaryInputError,
    validate_boundary_input,
)
from optimization.optimizer import OptimizationSequence

from integration.chain import PerceptionChain
from integration.mocks import MockDetector, MockHandTracker
from shared.config import (
    DetectorConfig,
    HandTrackerConfig,
    PipelineConfig,
    StabilizationConfig,
)
from shared.schemas.frame_packet import FramePacket
from shared.schemas.object_frame import ObjectFrame
from shared.schemas.observations import BoundingBox, Detection, HandObservation, Point2D


def source(frame_id):
    return FramePacket(
        frame_id, frame_id / 30, np.zeros((100, 100, 3), np.uint8), 100, 100
    )


def test_boundary_accepts_confirming_missing_and_expired_packets():
    optimizer = OptimizationSequence(StabilizationConfig(detection_min_frames=2))
    for i, seen in enumerate([True, True, False, False, False]):
        image = source(i)
        objects = ObjectFrame(
            i,
            image.timestamp_s,
            100,
            100,
            [Detection(0, "vial", 0.9, BoundingBox(10, 10, 30, 30), 7)] if seen else [],
        )
        packet = optimizer.process(objects)
        validate_boundary_input(packet, image)
        if i in (2, 3):
            assert packet.stable_detections and not packet.stable_detections[0].observed
            assert not packet.object_frame.detections
            assert not packet.quality_ok and packet.quality_reasons
        elif i == 4:
            assert not packet.stable_detections


def test_complete_stage_chain_to_real_boundary_validator():
    config = PipelineConfig(
        detector=DetectorConfig(backend="mock"),
        hand_tracker=HandTrackerConfig(backend="mock"),
    )
    detection = Detection(0, "vial", 0.9, BoundingBox(10, 10, 30, 30), 7)
    hand = HandObservation("hand", None, 0.8, [Point2D(20, 20)], Point2D(20, 20), True)
    with PerceptionChain(
        config,
        detector=MockDetector([[detection]]),
        hand_tracker=MockHandTracker([[hand]]),
    ) as chain:
        for i in range(5):
            result = chain.process(source(i))
            validate_boundary_input(result.optimization, result.prepared.source)
    assert result.optimization.interactions
    assert result.optimization.stable_detections[0].track_id == 7
    assert (
        result.optimization.observations.detections
        == result.optimization.object_frame.detections
    )


@pytest.mark.parametrize(
    "corruption",
    ["frame", "stable", "confidence", "presence", "count", "current", "order"],
)
def test_boundary_rejects_inconsistent_temporal_contract(corruption):
    optimizer = OptimizationSequence(StabilizationConfig(detection_min_frames=1))
    for i in range(2):
        packet = optimizer.process(
            ObjectFrame(
                i,
                i / 30,
                100,
                100,
                [Detection(0, "vial", 0.9, BoundingBox(10, 10, 30, 30), 7)],
            )
        )
    row = packet.temporal_window[-1]
    if corruption == "frame":
        packet.frame_id = 20
    elif corruption == "stable":
        packet.stable_detections = ()
    elif corruption in ("confidence", "presence"):
        evidence = replace(
            row.detections[0],
            **(
                {"confidence": float("nan")}
                if corruption == "confidence"
                else {"observed": False}
            ),
        )
        row = replace(row, detections=(evidence,))
        packet.temporal_window = (*packet.temporal_window[:-1], row)
    elif corruption == "count":
        packet.raw_detection_count += 1
    elif corruption == "current":
        packet.object_frame.detections[0].confidence = 0.2
    elif corruption == "order":
        packet.temporal_window = (row, row)
    with pytest.raises(BoundaryInputError):
        validate_boundary_input(packet, source(1))


def test_boundary_rejects_incorrect_types():
    with pytest.raises(BoundaryInputError):
        validate_boundary_input({}, source(0))
