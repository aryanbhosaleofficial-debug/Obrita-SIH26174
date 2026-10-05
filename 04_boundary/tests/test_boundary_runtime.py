"""Standalone runtime, safe state lifecycle, and error handling."""

import json
from dataclasses import asdict

import numpy as np
import pytest
from boundary.boundary_pipeline import BoundaryPipeline
from boundary.config import BoundaryConfig

from shared.enums.boundary_state import BoundaryState
from shared.enums.module_status import ModuleStatus
from shared.schemas.boundary_packet import BoundaryOutputPacket


def test_synthetic_frame_runs_without_mutation(image):
    original = image.copy()
    pipeline = BoundaryPipeline()
    packet = pipeline.process(image, 100, 1.25)
    assert type(packet) is BoundaryOutputPacket
    assert (packet.frame_id, packet.timestamp_s) == (100, 1.25)
    assert packet.contour_px and packet.chain_code and packet.differential_chain_code
    assert packet.area_px > 0 and packet.perimeter_px > 0
    assert sum(packet.chain_histogram) == pytest.approx(1)
    assert packet.quality_ok and packet.status == ModuleStatus.OK
    assert packet.boundary_state == BoundaryState.UNKNOWN and not packet.state_confirmed
    assert packet.orientation_deg_rack is None and packet.crosscheck_agrees is None
    np.testing.assert_array_equal(image, original)
    json.dumps(asdict(packet), allow_nan=False)


@pytest.mark.parametrize(
    "field,value",
    [
        ("frame", None),
        ("frame", np.zeros((2, 2, 4), np.uint8)),
        ("frame", np.zeros((2, 2), float)),
        ("frame_id", -1),
        ("frame_id", True),
        ("frame_id", 1.2),
        ("timestamp", float("nan")),
        ("timestamp", float("inf")),
        ("timestamp", -1),
        ("timestamp", True),
        ("hand_data", [[float("nan"), 0]]),
    ],
)
def test_invalid_raw_input_is_explicit(image, field, value):
    inputs = {"frame": image, "frame_id": 0, "timestamp": 0.0, "hand_data": None}
    inputs[field] = value
    pipeline = BoundaryPipeline()
    packet = pipeline.process(**inputs)
    assert packet.status == ModuleStatus.INVALID_INPUT
    assert not packet.quality_ok and packet.quality_reasons
    assert not pipeline.tracker.history
    json.dumps(asdict(packet), allow_nan=False)


def test_order_rejected_and_reset_replay_identical(image):
    pipeline = BoundaryPipeline()
    first = [asdict(pipeline.process(image, i, i / 30)) for i in range(3)]
    assert pipeline.process(image, 2, 2 / 30).status == ModuleStatus.INVALID_INPUT
    pipeline.reset()
    assert first == [asdict(pipeline.process(image, i, i / 30)) for i in range(3)]


@pytest.mark.parametrize(
    "roi",
    [
        (0, 0, -1, 5),
        (200, 200, 20, 20),
        (0, 0, float("nan"), 4),
        (0, 0, float("inf"), 4),
        42,
        (),
    ],
)
def test_invalid_roi(image, roi):
    packet = BoundaryPipeline().process(image, 0, 0, roi=roi)
    assert packet.status == ModuleStatus.INVALID_INPUT and packet.quality_reasons


def test_detection_bbox_is_xyxy_and_padding_applied_once(image):
    pipeline = BoundaryPipeline(roi_padding=3)
    packet = pipeline.process_detections(
        image,
        0,
        0,
        object_bbox=(30, 30, 90, 90),
        padding=5,
        target_object_track_id=7,
    )

    assert packet.target_object_track_id == 7 and packet.quality_ok
    assert packet.centroid_px == pytest.approx((60, 60))
    assert (
        pipeline.process_detections(image, 1, 1 / 30).status
        == ModuleStatus.NO_DETECTION
    )


@pytest.mark.parametrize(
    "bbox", [(40, 30, 20, 40), (30, 40, 40, 20), (0, 0, float("nan"), 50)]
)
def test_padding_cannot_make_invalid_detection_bbox_valid(image, bbox):
    packet = BoundaryPipeline().process_detections(
        image, 0, 0, object_bbox=bbox, padding=100
    )
    assert packet.status == ModuleStatus.INVALID_INPUT


def test_blank_scene_expires_tracking_without_stale_contour(image):
    pipeline = BoundaryPipeline()
    pipeline.process(image, 0, 0)
    blank = np.zeros_like(image)
    for i in range(1, 4):
        packet = pipeline.process(blank, i, i / 30)
        assert packet.status == ModuleStatus.NO_DETECTION and not packet.contour_px
    assert not pipeline.tracker.history


def test_rack_quality_requirement_is_honored_without_inventing_orientation(image):
    packet = BoundaryPipeline(
        config=BoundaryConfig(require_valid_rack_reference=True)
    ).process(image, 0, 0)
    assert packet.contour_px and not packet.quality_ok
    assert "valid rack reference required" in packet.quality_reasons
    assert packet.orientation_deg_rack is None


def test_standalone_explicit_reference_validity_unblocks_required_gate(image):
    pipeline = BoundaryPipeline(
        config=BoundaryConfig(require_valid_rack_reference=True)
    )
    packet = pipeline.process(image, 0, 0, rack_valid=True)
    assert packet.quality_ok and packet.orientation_deg_rack is None
    invalid = pipeline.process(image, 1, 1 / 30, rack_valid="yes")
    assert invalid.status == ModuleStatus.INVALID_INPUT
