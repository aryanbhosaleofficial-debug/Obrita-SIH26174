"""Hand proximity is gated by geometry; separation needs confirmed prior contact."""

import numpy as np
from boundary.boundary_pipeline import BoundaryPipeline
from boundary.config import BoundaryConfig

from shared.enums.boundary_state import BoundaryState


def hand(point):
    return [{"hand_id": "hand-1", "point": point}]


def test_hand_on_boundary_contact(image):
    pipeline = BoundaryPipeline()
    first = pipeline.process(image, 0, 0, hand_data=hand((35, 60)))
    assert first.hand_contact and not first.state_confirmed
    second = pipeline.process(image, 1, 1 / 30, hand_data=hand((35, 60)))
    assert second.boundary_state == BoundaryState.CONTACT and second.state_confirmed
    assert second.confirmed_frames == 2


def test_hand_far_no_contact(image):
    output = BoundaryPipeline().process(image, 0, 0, hand_data=hand((150, 110)))
    assert not output.hand_contact and output.contact_confidence == 0


def test_contact_is_evidence_only(image):
    output = BoundaryPipeline().process(image, 0, 0, hand_data=hand((35, 60)))
    assert output.hand_contact and not hasattr(output, "procedure_correct")


def test_low_quality_geometry_and_near_hand_publish_no_strong_contact(image):
    pipeline = BoundaryPipeline(
        config=BoundaryConfig(require_valid_rack_reference=True)
    )
    output = pipeline.process(image, 0, 0, hand_data=hand((35, 60)))
    assert output.contour_px and not output.quality_ok
    assert (
        output.confidence == 0
        and not output.hand_contact
        and output.contact_confidence == 0
    )
    assert not output.state_confirmed and not pipeline.tracker.history


def test_uniform_geometry_cannot_confirm_contact(image):
    pipeline = BoundaryPipeline()
    for i in range(6):
        output = pipeline.process(
            np.full_like(image, 127), i, i / 30, hand_data=hand((0, 0))
        )
        assert not output.hand_contact and output.contact_confidence == 0
        assert output.boundary_state == BoundaryState.UNKNOWN


def test_separation_requires_motion_after_confirmed_contact(image):
    pipeline = BoundaryPipeline()
    for i in range(3):
        contact = pipeline.process(image, i, i / 30, hand_data=hand((35, 60)))
    assert contact.boundary_state == BoundaryState.CONTACT and contact.state_confirmed
    released = []
    for i in range(3, 6):
        shifted = np.roll(image, 3 * (i - 2), axis=1)
        released.append(pipeline.process(shifted, i, i / 30, hand_data=hand((3, 60))))
    assert any(
        p.boundary_state == BoundaryState.SEPARATING and p.state_confirmed
        for p in released
    )


def test_hand_disappearance_or_stationary_release_is_not_separation(image):
    for data in (None, hand((3, 60))):
        pipeline = BoundaryPipeline()
        for i in range(3):
            pipeline.process(image, i, i / 30, hand_data=hand((35, 60)))
        for i in range(3, 7):
            output = pipeline.process(image, i, i / 30, hand_data=data)
            assert output.boundary_state != BoundaryState.SEPARATING


def test_unidentified_hand_cannot_create_separation_transition(image):
    pipeline = BoundaryPipeline()
    for i in range(3):
        packet = pipeline.process(
            image, i, i / 30, hand_data=[{"hand_id": None, "point": (35, 60)}]
        )
    assert packet.boundary_state == BoundaryState.CONTACT
    for i in range(3, 6):
        packet = pipeline.process(
            np.roll(image, 3 * (i - 2), axis=1),
            i,
            i / 30,
            hand_data=[{"hand_id": None, "point": (3, 60)}],
        )
        assert packet.boundary_state != BoundaryState.SEPARATING
