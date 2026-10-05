"""Real Module 01 -> 02 -> 03 contracts with an injected model-free detector."""

from dataclasses import replace

import numpy as np
import pytest
from optimization.optimizer import OptimizationSequence
from optimization.pipeline import OptimizationPipeline
from yolo.pipeline import YoloPipeline

from integration.mocks import MockDetector
from perception.core import FrameProcessor
from shared.config import (
    DetectorConfig,
    HandTrackerConfig,
    PipelineConfig,
    PreprocessingConfig,
    StabilizationConfig,
)
from shared.schemas.frame_packet import FramePacket
from shared.schemas.object_frame import ObjectFrame
from shared.schemas.observations import BoundingBox, Detection


def make_stages():
    core = FrameProcessor(PreprocessingConfig(max_width=160))
    detector = MockDetector(
        [[Detection(4, "vial", 0.8, BoundingBox(20, 10, 40, 30), 12)]]
    )
    yolo = YoloPipeline(DetectorConfig(backend="mock"), detector=detector)
    return core, yolo


def test_canonical_yolo_packet_accepted_without_adapter():
    core, yolo = make_stages()
    optimizer = OptimizationSequence()
    with yolo:
        for i in range(3):
            source = FramePacket(
                i,
                i / 30,
                np.zeros((240, 320, 3), np.uint8),
                320,
                240,
                source_id="video",
                session_id="test",
            )
            objects = yolo.process(core.process(source))
            assert type(objects) is ObjectFrame
            output = optimizer.process(objects)
    assert output.stable_detections[0].track_id == 12
    assert output.stable_detections[0].class_name == "vial"
    assert output.stable_detections[0].confidence == pytest.approx(0.8)
    assert output.source_id == "video" and output.session_id == "test"


def test_source_coordinates_and_metadata_preserved():
    core, yolo = make_stages()
    with yolo:
        source = FramePacket(10, 1.2, np.zeros((240, 320, 3), np.uint8), 320, 240)
        prepared = core.process(source)
        objects = yolo.process(prepared)
    output = OptimizationSequence(StabilizationConfig(detection_min_frames=1)).process(
        objects
    )
    assert output.object_frame.detections[0].bbox == BoundingBox(40, 20, 80, 60)
    assert (output.frame_id, output.timestamp_s) == (10, 1.2)
    assert (output.object_frame.image_width, output.object_frame.image_height) == (
        320,
        240,
    )
    assert output.object_frame.stage_timings_ms == objects.stage_timings_ms
    assert output.object_frame.reference_anchors == objects.reference_anchors == []


def test_spatial_wrapper_rejects_mismatched_source_metadata():
    core, yolo = make_stages()
    with yolo:
        prepared = core.process(
            FramePacket(0, 0, np.zeros((240, 320, 3), np.uint8), 320, 240)
        )
        objects = yolo.process(prepared)
    wrapper = OptimizationPipeline(
        PipelineConfig(hand_tracker=HandTrackerConfig(enabled=False, backend="none"))
    )
    with pytest.raises(ValueError, match="metadata"):
        wrapper.process(prepared, replace(objects, frame_id=1))
    wrapper.close()


def test_spatial_wrapper_and_image_free_api_share_temporal_results():
    config = PipelineConfig(
        hand_tracker=HandTrackerConfig(enabled=False, backend="none")
    )
    wrapper, optimizer = (
        OptimizationPipeline(config),
        OptimizationSequence(config.stabilization),
    )
    core, yolo = make_stages()
    try:
        with yolo:
            for i in range(5):
                prepared = core.process(
                    FramePacket(i, i / 30, np.zeros((240, 320, 3), np.uint8), 320, 240)
                )
                objects = yolo.process(prepared)
                spatial = wrapper.process(prepared, objects)
                temporal = optimizer.process(objects)
                assert spatial.temporal_window == temporal.temporal_window
                assert spatial.stable_detections == temporal.stable_detections
    finally:
        wrapper.close()
