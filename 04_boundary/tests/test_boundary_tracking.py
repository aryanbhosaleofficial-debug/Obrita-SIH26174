"""Bounded motion and N-of-M temporal-state regressions."""

import numpy as np
import pytest
from boundary.boundary_pipeline import BoundaryPipeline
from boundary.temporal.confirmation import StateConfirmation

from shared.enums.boundary_state import BoundaryState as State


def test_stationary_object(image):
    pipeline = BoundaryPipeline()
    outputs = [pipeline.process(image, i, i / 30) for i in range(5)]
    assert not outputs[0].state_confirmed and not outputs[2].state_confirmed
    assert outputs[3].boundary_state == State.STATIONARY and outputs[3].state_confirmed
    assert outputs[-1].confirmed_frames == 3


def test_translating_object(image):
    pipeline = BoundaryPipeline()
    outputs = [
        pipeline.process(np.roll(image, 3 * i, axis=1), i, i / 30) for i in range(5)
    ]
    assert outputs[-1].boundary_state == State.MOVING and outputs[-1].state_confirmed
    assert outputs[-1].confirmed_frames >= 2


@pytest.mark.skip(
    reason="Rack-relative ROTATING unsupported; no camera-axis substitute"
)
def test_rotating_object():
    pass


def test_target_change_resets_history(image):
    pipeline = BoundaryPipeline()
    for i in range(5):
        pipeline.process(image, i, i / 30, target_object_track_id=7)
    output = pipeline.process(image, 5, 5 / 30, target_object_track_id=8)
    assert len(pipeline.tracker.history) == 1 and not output.state_confirmed
    assert output.boundary_state == State.UNKNOWN


def test_confirmation_required_and_n_of_m_is_not_consecutive_only():
    confirm = StateConfirmation(n=3, m=5)
    outputs = [
        confirm.update(s)
        for s in (
            State.CONTACT,
            State.UNKNOWN,
            State.CONTACT,
            State.MOVING,
            State.CONTACT,
        )
    ]
    assert all(not result[1] for result in outputs[:-1])
    assert outputs[-1] == (State.CONTACT, True, 3)
    assert confirm.update(State.STATIONARY) == (State.UNKNOWN, False, 0)
    assert len(confirm.history) == 5
    confirm.reset()
    assert not confirm.history


def test_one_centroid_spike_does_not_confirm_movement(image):
    pipeline = BoundaryPipeline()
    offsets = [0, 0, 0, 9, 0, 0, 0]
    outputs = [
        pipeline.process(np.roll(image, offset, axis=1), i, i / 30)
        for i, offset in enumerate(offsets)
    ]
    assert all(p.boundary_state != State.MOVING for p in outputs)


def test_bad_geometry_invalidates_state_confirmation(image):
    pipeline = BoundaryPipeline()
    for i in range(5):
        output = pipeline.process(image, i, i / 30)
    assert output.state_confirmed
    bad = pipeline.process(np.full_like(image, 127), 5, 5 / 30)
    assert not bad.state_confirmed and bad.confirmed_frames == 0
    assert not pipeline.state_classifier.confirmation.history
    recovered = pipeline.process(image, 6, 6 / 30)
    assert not recovered.state_confirmed


def test_gap_and_reset_do_not_reuse_old_state_votes(image):
    pipeline = BoundaryPipeline()
    for i in range(5):
        pipeline.process(image, i, i / 30)
    packet = pipeline.process(image, 8, 8 / 30)
    assert not packet.state_confirmed
    pipeline.reset()
    assert not pipeline.state_classifier.confirmation.history
    assert not pipeline.state_classifier.centroids


def test_state_memory_is_bounded_and_confirmed_replay_deterministic(image):
    from dataclasses import asdict

    pipeline = BoundaryPipeline()
    first = [asdict(pipeline.process(image, i, i / 30)) for i in range(8)]
    pipeline.reset()
    assert first == [asdict(pipeline.process(image, i, i / 30)) for i in range(8)]
    for i in range(8, 80):
        pipeline.process(image, i, i / 30)
        assert len(pipeline.tracker.history) <= pipeline.config.history_frames
        assert (
            len(pipeline.state_classifier.centroids)
            <= pipeline.config.motion_min_frames
        )
        assert (
            len(pipeline.state_classifier.confirmation.history)
            <= pipeline.config.confirmation_m
        )
