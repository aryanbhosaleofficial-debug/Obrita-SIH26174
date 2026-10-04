from copy import deepcopy
from dataclasses import replace

import numpy as np
import pytest

from perception import PerceptionPipeline
from perception.contracts import (
    CoordinateFrame,
    Point2D,
    PoseObservation,
    ReferenceFrameInfo,
)
from perception.detector import InitializationError
from perception.integration import to_object_frame
from perception.mocks import MockDetector, MockHandTracker
from perception.visualization import draw_perception_overlay
from shared.enums.module_status import ModuleStatus


def test_valid_frame_timings_identity_and_source_untouched(pipeline, packet):
    source = packet()
    original = source.image.copy()
    result = pipeline.process(source)
    assert result.status == ModuleStatus.OK
    assert result.frame_id == source.frame_id and result.timestamp == source.timestamp_s
    assert result.source_id == source.source_id
    assert result.coordinate_frame_valid
    assert result.association_coordinate_frame == CoordinateFrame.RACK_RELATIVE
    assert result.detections[0].reference_polygon
    assert result.hands[0].reference_landmarks
    assert all(value >= 0 for value in result.stage_timings_ms.values())
    assert result.processing_time_ms == result.stage_timings_ms["total_ms"]
    assert (
        sum(v for k, v in result.stage_timings_ms.items() if k != "total_ms")
        <= result.processing_time_ms
    )
    overlay = draw_perception_overlay(source.image, result)
    assert np.array_equal(source.image, original) and not np.array_equal(
        overlay, original
    )
    assert not result.reliable_for_temporal_reasoning
    for i in range(1, 4):
        result = pipeline.process(packet(i))
    assert result.reliable_for_temporal_reasoning


def test_no_objects_and_no_hands(config, packet, scene):
    d, h = scene
    for detections, hands in [([], h), (d, []), ([], [])]:
        with PerceptionPipeline(
            config,
            detector=MockDetector([detections]),
            hand_tracker=MockHandTracker([hands]),
        ) as pipeline:
            result = pipeline.process(packet())
        assert result.interactions == []
        if not detections:
            assert "no_objects" in result.warnings
        if not hands:
            assert "no_hands" in result.warnings
        if not detections and not hands:
            assert result.status == ModuleStatus.NO_DETECTION


def test_invalid_frame_does_not_initialize_models(pipeline, packet):
    result = pipeline.process(replace(packet(), image=None))
    assert result.status == ModuleStatus.INVALID_INPUT
    assert not pipeline._initialized
    assert result.interactions == [] and not result.coordinate_frame_valid


class FailingDetector(MockDetector):
    def detect(self, image):
        raise RuntimeError("simulated inference failure")


class FailingHands(MockHandTracker):
    def track(self, image):
        raise RuntimeError("simulated tracker failure")


@pytest.mark.parametrize("failed", ["detector", "hands"])
def test_runtime_backend_failure_returns_warning(config, packet, scene, failed):
    d, h = scene
    with PerceptionPipeline(
        config,
        detector=FailingDetector() if failed == "detector" else MockDetector([d]),
        hand_tracker=FailingHands() if failed == "hands" else MockHandTracker([h]),
    ) as pipeline:
        result = pipeline.process(packet())
    assert result.status == ModuleStatus.DEGRADED
    assert any("failure" in w for w in result.warnings)
    assert result.interactions == []
    assert bool(result.hands) == (failed == "detector")
    assert bool(result.detections) == (failed == "hands")


class FailingReference:
    def update(self, image):
        raise RuntimeError("rack not visible")

    def image_to_reference(self, point, frame_shape):
        raise AssertionError("must not transform when reference unavailable")


def test_reference_failure_falls_back_explicitly(config, packet, scene):
    d, h = scene
    with PerceptionPipeline(
        config,
        detector=MockDetector([d]),
        hand_tracker=MockHandTracker([h]),
        coordinate_transformer=FailingReference(),
    ) as pipeline:
        result = pipeline.process(packet())
    assert not result.coordinate_frame_valid
    assert result.detections[0].reference_polygon is None
    assert result.hands[0].reference_landmarks is None
    assert result.associations[0].coordinate_frame == CoordinateFrame.NORMALIZED_IMAGE
    assert "reference_frame_unavailable" in result.warnings


def test_partial_reference_failure_discards_all_reference_coordinates(
    config, packet, scene
):
    class PartialReference:
        def update(self, image):
            return ReferenceFrameInfo(True, "test")

        def image_to_reference(self, point, frame_shape):
            if point.x == 150:
                raise RuntimeError("transform failed for palm")
            return Point2D(point.x / 320, point.y / 240)

    d, h = scene
    with PerceptionPipeline(
        config,
        detector=MockDetector([d]),
        hand_tracker=MockHandTracker([h]),
        coordinate_transformer=PartialReference(),
    ) as pipeline:
        result = pipeline.process(packet())
    assert not result.coordinate_frame_valid
    assert all(d.reference_polygon is None for d in result.detections)
    assert all(h.reference_palm_center is None for h in result.hands)


def test_calibration_loss_and_recovery_restart_interactions(pipeline, packet):
    for i in range(4):
        result = pipeline.process(packet(i))
    assert result.interactions
    pipeline.coordinate_transformer.valid = False
    result = pipeline.process(packet(4))
    assert not result.interactions
    pipeline.coordinate_transformer.valid = True
    result = pipeline.process(packet(5))
    assert not result.interactions and result.detections[0].motion.value == "unknown"


def test_ordering_source_reset_and_long_gap(pipeline, packet):
    pipeline.process(packet())
    for source in [packet(), packet(1, timestamp=0), packet(1, source="other")]:
        assert pipeline.process(source).status == ModuleStatus.INVALID_INPUT
    for i in range(1, 4):
        result = pipeline.process(packet(i))
    assert result.interactions
    result = pipeline.process(packet(100, timestamp=10))
    assert not result.detections[0].is_stable and not result.interactions
    assert "temporal_history_reset" in result.warnings
    pipeline.reset()
    assert pipeline.process(packet(source="other")).status == ModuleStatus.OK


def test_frame_id_gaps_age_confirmation(pipeline, packet):
    pipeline.process(packet(0))
    pipeline.process(packet(1))
    result = pipeline.process(packet(3))
    assert not result.detections[0].is_stable
    assert "source_frames_missing: 1" in result.warnings


def test_failed_initialization_closes_all_acquired_backends(config, packet, scene):
    class BadInit(MockHandTracker):
        def initialize(self):
            raise RuntimeError("cannot load task")

    detector, hands = MockDetector([scene[0]]), BadInit()
    pipeline = PerceptionPipeline(config, detector=detector, hand_tracker=hands)
    with pytest.raises(InitializationError, match="cannot load task"):
        pipeline.process(packet())
    assert detector.closed and hands.closed
    pipeline.close()
    pipeline.close()
    with pytest.raises(InitializationError, match="closed"):
        pipeline.initialize()


def test_injected_pose_interface(config, packet, scene):
    class Pose:
        def initialize(self):
            pass

        def close(self):
            pass

        def track(self, image):
            return [PoseObservation([Point2D(160, 120)], 0.7)]

    with PerceptionPipeline(
        config,
        detector=MockDetector([scene[0]]),
        hand_tracker=MockHandTracker([scene[1]]),
        pose_tracker=Pose(),
    ) as pipeline:
        result = pipeline.process(packet())
    assert result.poses[0].reference_landmarks == [Point2D(0.5, 0.5)]


def test_object_frame_bridge_does_not_invent_ids_or_anchors(pipeline, packet):
    result = pipeline.process(packet())
    result.detections[0].track_id = None
    original = deepcopy(result)
    objects = to_object_frame(result)
    assert (
        objects.frame_id == result.frame_id
        and objects.timestamp_s == result.timestamp_s
    )
    assert objects.detections[0].bbox_xyxy == (120, 80, 200, 160)
    assert objects.detections[0].track_id is None and objects.reference_anchors == []
    assert objects.detections[0].track_age_frames == 0
    assert result == original
