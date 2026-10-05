"""Final reviewed blockers: defaults, dropped-frame tolerance and motion scaling."""

from pathlib import Path

import numpy as np
import pytest
from boundary.boundary_pipeline import BoundaryPipeline
from boundary.config import BoundaryConfig

from shared.enums.boundary_state import BoundaryState
from shared.enums.module_status import ModuleStatus


def test_python_yaml_and_runtime_padding_defaults_agree():
    yaml_config = BoundaryConfig.from_yaml(
        Path(__file__).resolve().parents[2] / "configs/boundary.yaml"
    )
    assert BoundaryConfig().padding_ratio == yaml_config.padding_ratio == 0.1
    assert BoundaryPipeline().config.padding_ratio == 0.1


@pytest.mark.parametrize("stride", [1, 2, 3])
def test_stationary_confirms_with_tolerated_drops(image, stride):
    pipeline = BoundaryPipeline(config=BoundaryConfig(max_missing_frames=2))
    for frame_id in range(0, 5 * stride, stride):
        packet = pipeline.process(image, frame_id, frame_id / 30)
    assert packet.boundary_state == BoundaryState.STATIONARY and packet.state_confirmed
    assert packet.confirmed_frames == 3


@pytest.mark.parametrize("frame_ids", [(0, 2, 4, 6, 8), (0, 1, 3, 6, 7)])
def test_moving_confirms_with_tolerated_drops(image, frame_ids):
    pipeline = BoundaryPipeline()
    for frame_id in frame_ids:
        pixels = np.roll(image, 3 * frame_id, axis=1)
        packet = pipeline.process(pixels, frame_id, frame_id / 30)
    assert packet.boundary_state == BoundaryState.MOVING and packet.state_confirmed


def test_dropped_frames_do_not_turn_slow_motion_into_fast_motion(image):
    pipeline = BoundaryPipeline()
    for frame_id in (0, 2, 4, 6, 8):
        packet = pipeline.process(
            np.roll(image, frame_id, axis=1), frame_id, frame_id / 30
        )
    # Two pixels over two source frames = one pixel/frame, not MOVING.
    assert packet.boundary_state == BoundaryState.STATIONARY and packet.state_confirmed


@pytest.mark.parametrize(
    "max_missing,next_id,expected", [(2, 7, True), (2, 8, False), (0, 6, False)]
)
def test_missing_count_boundary_and_large_gap_reset(
    image, max_missing, next_id, expected
):
    pipeline = BoundaryPipeline(config=BoundaryConfig(max_missing_frames=max_missing))
    for frame_id in range(5):
        pipeline.process(image, frame_id, frame_id / 30)
    # Previous ID is 4: ID 7 means exactly two missing frames, ID 8 means three.
    packet = pipeline.process(image, next_id, next_id / 30)
    assert packet.state_confirmed is expected
    assert packet.boundary_state == (
        BoundaryState.STATIONARY if expected else BoundaryState.UNKNOWN
    )
    if not expected:
        assert len(pipeline.state_classifier.centroids) == 1
        assert len(pipeline.state_classifier.confirmation.history) == 1


def test_time_gap_still_resets_even_with_tolerated_missing_count(image):
    pipeline = BoundaryPipeline()
    for frame_id in range(5):
        pipeline.process(image, frame_id, frame_id / 30)
    packet = pipeline.process(image, 6, 2.0)
    assert not packet.state_confirmed
    assert len(pipeline.state_classifier.centroids) == 1


@pytest.mark.parametrize("frame_id,timestamp", [(4, 5 / 30), (3, 5 / 30), (5, 4 / 30)])
def test_duplicate_backward_id_and_timestamp_rejection_preserved(
    image, frame_id, timestamp
):
    pipeline = BoundaryPipeline()
    for index in range(5):
        pipeline.process(image, index, index / 30)
    before = (
        pipeline._frame_id,
        pipeline._timestamp,
        list(pipeline.state_classifier.centroids),
        list(pipeline.state_classifier.confirmation.history),
    )
    rejected = pipeline.process(image, frame_id, timestamp)
    assert rejected.status == ModuleStatus.INVALID_INPUT
    assert not rejected.state_confirmed and rejected.confidence == 0
    assert before == (
        pipeline._frame_id,
        pipeline._timestamp,
        list(pipeline.state_classifier.centroids),
        list(pipeline.state_classifier.confirmation.history),
    )
