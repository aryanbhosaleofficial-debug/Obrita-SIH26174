"""Shared packet and safety invariants; no private packet or dynamic fields."""

import pytest
from boundary.boundary_pipeline import BoundaryPipeline
from boundary.output.boundary_packet_builder import build_packet

from shared.enums.boundary_state import BoundaryState
from shared.schemas.boundary_packet import BoundaryOutputPacket


def test_metadata_copied_unchanged(image):
    output = BoundaryPipeline().process(
        image, 23, 1.4, target_track_id=99, target_object_track_id=7
    )
    assert (
        output.frame_id,
        output.timestamp_s,
        output.target_track_id,
        output.target_object_track_id,
    ) == (23, 1.4, 99, 7)


def test_uses_shared_schema(image):
    assert type(BoundaryPipeline().process(image, 0, 0)) is BoundaryOutputPacket


@pytest.mark.skip(reason="Optimization cross-check remains explicitly disabled")
def test_crosscheck_does_not_overwrite():
    pass


def test_quality_reasons_recorded():
    output = build_packet(frame_id=0, timestamp=0, quality={"quality_ok": False})
    assert not output.quality_ok and output.quality_reasons


def test_rejected_quality_cannot_publish_confidence_contact_or_confirmed_state():
    output = build_packet(
        frame_id=0,
        timestamp=0,
        quality={"quality_ok": False, "confidence": 0.99},
        interaction={"near_boundary": True, "contact_proxy": 0.99},
        boundary_state=BoundaryState.CONTACT,
        state_confirmed=True,
        confirmed_frames=10,
    )
    assert output.confidence == 0
    assert not output.hand_contact and output.contact_confidence == 0
    assert output.boundary_state == BoundaryState.UNKNOWN
    assert not output.state_confirmed and output.confirmed_frames == 0
