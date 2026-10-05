"""Real Module 03 packets -> recovered Module 04 -> unchanged shared output."""

import json
from dataclasses import asdict, replace

import cv2
import numpy as np
import pytest
from boundary.boundary_pipeline import BoundaryPipeline
from boundary.config import BoundaryConfig
from boundary.input.contract_validator import BoundaryInputError

from optimization import OptimizationSequence
from shared.enums.boundary_state import BoundaryState
from shared.enums.module_status import ModuleStatus
from shared.schemas.boundary_packet import BoundaryOutputPacket
from shared.schemas.frame_packet import FramePacket
from shared.schemas.object_frame import ObjectFrame
from shared.schemas.observations import BoundingBox, Detection, HandObservation, Point2D


def scene(frame_id, *, tracks=(7,), source_id="test", color_format="BGR"):
    image = np.zeros((120, 160, 3), np.uint8)
    cv2.rectangle(image, (35, 35), (85, 85), (255, 255, 255), -1)
    frame = FramePacket(
        frame_id,
        frame_id / 30,
        image,
        160,
        120,
        source_id=source_id,
        color_format=color_format,
    )
    objects = ObjectFrame(
        frame_id,
        frame.timestamp_s,
        160,
        120,
        [
            Detection(0, "vial", 0.9, BoundingBox(30, 30, 90, 90), track)
            for track in tracks
        ],
        source_id=source_id,
    )
    return frame, objects


def test_actual_module03_to_boundary_runtime_and_identity():
    optimizer, boundary = OptimizationSequence(), BoundaryPipeline()
    for i in range(3):
        frame, objects = scene(i)
        optimized = optimizer.process(objects)
        optimized.target_track_id = 99  # Distinct operator and object identities.
        output = boundary.process_optimization(optimized, frame)
        assert (output.frame_id, output.timestamp_s, output.target_track_id) == (
            i,
            i / 30,
            99,
        )
    assert type(output) is BoundaryOutputPacket and output.quality_ok
    assert output.target_object_track_id == 7
    assert output.contour_px and output.chain_code and output.chain_histogram
    assert output.boundary_state == BoundaryState.UNKNOWN and not output.state_confirmed
    assert output.orientation_deg_rack is None and output.crosscheck_agrees is None


def test_held_objects_are_never_analyzed_as_fresh_boundaries():
    optimizer, boundary = OptimizationSequence(), BoundaryPipeline()
    for i in range(3):
        frame, objects = scene(i)
        boundary.process_optimization(optimizer.process(objects), frame)
    frame, objects = scene(3, tracks=())
    optimized = optimizer.process(objects)
    assert optimized.stable_detections and not optimized.stable_detections[0].observed
    output = boundary.process_optimization(optimized, frame)
    assert output.status == ModuleStatus.NO_DETECTION and not output.contour_px


def test_explicit_target_and_ambiguity():
    optimizer, boundary = OptimizationSequence(), BoundaryPipeline()
    for i in range(3):
        frame, objects = scene(i, tracks=(7, 8))
        optimized = optimizer.process(objects)
    absent = boundary.process_optimization(optimized, frame)
    assert absent.status == ModuleStatus.NO_DETECTION
    frame, objects = scene(3, tracks=(7, 8))
    optimized = optimizer.process(objects)
    selected = boundary.process_optimization(optimized, frame, target_object_track_id=8)
    assert selected.target_object_track_id == 8 and selected.quality_ok


def test_frame_mismatch_rejected_before_tracking_changes():
    frame, objects = scene(0)
    optimized = OptimizationSequence().process(objects)
    boundary = BoundaryPipeline()
    with pytest.raises(BoundaryInputError):
        boundary.process_optimization(optimized, replace(frame, frame_id=10))
    assert not boundary.tracker.history and boundary._frame_id is None


def test_target_change_restarts_geometry_history():
    optimizer, boundary = OptimizationSequence(), BoundaryPipeline()
    for i in range(3):
        frame, objects = scene(i, tracks=(7, 8))
        boundary.process_optimization(
            optimizer.process(objects), frame, target_object_track_id=7
        )
    frame, objects = scene(3, tracks=(7, 8))
    boundary.process_optimization(
        optimizer.process(objects), frame, target_object_track_id=8
    )
    assert len(boundary.tracker.history) == 1


def test_image_and_packet_are_not_mutated():
    optimizer, boundary = OptimizationSequence(), BoundaryPipeline()
    for i in range(3):
        frame, objects = scene(i)
        optimized = optimizer.process(objects)
    before_pixels, before_packet = frame.image.copy(), asdict(optimized)
    output = boundary.process_optimization(optimized, frame)
    np.testing.assert_array_equal(frame.image, before_pixels)
    assert asdict(optimized) == before_packet
    wire = json.loads(json.dumps(asdict(output), allow_nan=False))
    # This proves the unchanged shared consumer contract, not a Module 05
    # algorithm: the actual Module 05 implementation is still scaffolded.
    wire["status"] = ModuleStatus(wire["status"])
    wire["boundary_state"] = BoundaryState(wire["boundary_state"])
    restored = BoundaryOutputPacket(**wire)
    assert restored.target_object_track_id == 7 and restored.quality_ok


def test_yaml_rack_requirement_produces_explicit_quality_reason():
    from pathlib import Path

    boundary = BoundaryPipeline.from_yaml(
        Path(__file__).resolve().parents[1] / "configs/boundary.yaml"
    )
    optimizer = OptimizationSequence()
    for i in range(3):
        frame, objects = scene(i)
        output = boundary.process_optimization(optimizer.process(objects), frame)
    assert output.contour_px and not output.quality_ok
    assert "valid rack reference required" in output.quality_reasons


def test_rgb_source_conversion_and_current_pixel_geometry():
    boundary = BoundaryPipeline(
        config=BoundaryConfig(segmentation_params={"threshold": 50}, blur_kernel=0)
    )
    optimizer = OptimizationSequence()
    for i in range(3):
        frame, objects = scene(i, color_format="RGB")
        frame.image[:, :] = 0
        frame.image[35:86, 35:86] = (255, 0, 0)  # Red in source RGB.
        output = boundary.process_optimization(optimizer.process(objects), frame)
    assert output.quality_ok and output.centroid_px == pytest.approx((60, 60))


@pytest.mark.parametrize(
    "scenario", ["bright", "dark", "grey", "black", "noise", "fill", "border"]
)
def test_reviewed_segmentation_cases_through_actual_module03(scenario):
    optimizer, boundary = OptimizationSequence(), BoundaryPipeline()
    for i in range(5):
        frame, objects = scene(i)
        if scenario == "dark":
            frame.image[:] = 255 - frame.image
        elif scenario == "grey":
            frame.image[:] = 127
        elif scenario == "black":
            frame.image[:] = 0
        elif scenario == "noise":
            frame.image[:] = np.random.default_rng(i).integers(
                0, 256, frame.image.shape, dtype=np.uint8
            )
        elif scenario == "fill":
            frame.image[:] = 0
            # Fill the actual padded ROI, not a legitimate tight object box.
            frame.image[24:96, 24:96] = 255
        elif scenario == "border":
            frame.image[:] = 0
            cv2.rectangle(frame.image, (24, 24), (95, 95), (255, 255, 255), 1)
        optimized = optimizer.process(objects)
        optimized.target_track_id = 99
        before_packet = asdict(optimized)
        before_pixels = frame.image.copy()
        output = boundary.process_optimization(optimized, frame)
        assert type(output) is BoundaryOutputPacket
        assert (output.frame_id, output.timestamp_s, output.target_track_id) == (
            i,
            i / 30,
            99,
        )
        np.testing.assert_array_equal(frame.image, before_pixels)
        assert asdict(optimized) == before_packet
    assert output.target_object_track_id == 7
    if scenario in ("bright", "dark"):
        assert output.quality_ok and output.centroid_px == pytest.approx((60, 60))
        assert output.area_px == pytest.approx(2500, abs=10)
    else:
        assert not output.quality_ok and output.confidence == 0
        assert not output.hand_contact and output.contact_confidence == 0
        assert not output.state_confirmed


def test_invalid_geometry_suppresses_real_upstream_hand_evidence():
    optimizer = OptimizationSequence()
    boundary = BoundaryPipeline(
        config=BoundaryConfig(require_valid_rack_reference=True)
    )
    for i in range(4):
        frame, objects = scene(i)
        optimized = optimizer.process(objects)
        point = Point2D(35, 60)
        hands = [HandObservation("hand-1", None, 0.9, [point], point)]
        optimized.spatial.hands = hands
        optimized.observations.hands = hands
        before = asdict(optimized)
        output = boundary.process_optimization(optimized, frame)
        assert asdict(optimized) == before
    assert output.contour_px and not output.quality_ok
    assert (
        output.confidence == output.contact_confidence == 0 and not output.hand_contact
    )
    assert not output.state_confirmed


def test_stationary_state_is_confirmed_through_actual_module03():
    optimizer, boundary = OptimizationSequence(), BoundaryPipeline()
    for i in range(7):
        frame, objects = scene(i)
        output = boundary.process_optimization(optimizer.process(objects), frame)
    assert output.boundary_state == BoundaryState.STATIONARY and output.state_confirmed
    assert output.confirmed_frames == 3


@pytest.mark.parametrize("change", ["source", "session"])
def test_new_stream_requires_explicit_boundary_reset(change):
    optimizer, boundary = OptimizationSequence(), BoundaryPipeline()
    for i in range(3):
        frame, objects = scene(i)
        boundary.process_optimization(optimizer.process(objects), frame)
    previous = (boundary._stream, boundary._frame_id, len(boundary.tracker.history))
    optimizer.reset()
    for i in range(3):
        frame, objects = scene(i, source_id="new" if change == "source" else "test")
        if change == "session":
            frame.session_id = objects.session_id = "new-session"
        optimized = optimizer.process(objects)
    rejected = boundary.process_optimization(optimized, frame)
    assert rejected.status == ModuleStatus.INVALID_INPUT
    assert "explicit reset" in rejected.quality_reasons[0]
    assert (
        boundary._stream,
        boundary._frame_id,
        len(boundary.tracker.history),
    ) == previous
    boundary.reset()
    accepted = boundary.process_optimization(optimized, frame)
    assert accepted.quality_ok and len(boundary.tracker.history) == 1


@pytest.mark.parametrize("kind", ["moving", "contact", "separating"])
def test_supported_states_through_actual_module03(kind):
    optimizer, boundary = OptimizationSequence(), BoundaryPipeline()
    outputs = []
    for i in range(9):
        frame, objects = scene(i)
        offset = (
            3 * i
            if kind == "moving"
            else 3 * max(0, i - 5)
            if kind == "separating"
            else 0
        )
        frame.image[:] = np.roll(frame.image, offset, axis=1)
        objects.detections[0].bbox = BoundingBox(30 + offset, 30, 90 + offset, 90)
        optimized = optimizer.process(objects)
        if kind != "moving":
            point = Point2D(3 if kind == "separating" and i > 5 else 35, 60)
            hands = [
                HandObservation("hand-1", None, 0.9, [point], point, continuity_key=12)
            ]
            optimized.spatial.hands = optimized.observations.hands = hands
        outputs.append(boundary.process_optimization(optimized, frame))
    expected = {
        "moving": BoundaryState.MOVING,
        "contact": BoundaryState.CONTACT,
        "separating": BoundaryState.SEPARATING,
    }[kind]
    assert outputs[-1].boundary_state == expected and outputs[-1].state_confirmed
    assert outputs[-1].confirmed_frames >= 2


@pytest.mark.parametrize(
    "position", [(35, 35), (0, 35), (109, 35), (35, 0), (35, 69), (0, 0), (109, 69)]
)
@pytest.mark.parametrize("dark_object", [False, True])
def test_tight_yolo_bbox_and_image_edge_padding_through_module03(position, dark_object):
    optimizer, boundary = OptimizationSequence(), BoundaryPipeline()
    x, y = position
    for frame_id in range(5):
        frame, objects = scene(frame_id)
        frame.image[:] = 255 if dark_object else 0
        frame.image[y : y + 51, x : x + 51] = 0 if dark_object else 255
        objects.detections[0].bbox = BoundingBox(x, y, x + 51, y + 51)
        optimized = optimizer.process(objects)
        before_packet, before_pixels = asdict(optimized), frame.image.copy()
        output = boundary.process_optimization(optimized, frame)
        assert asdict(optimized) == before_packet
        np.testing.assert_array_equal(frame.image, before_pixels)
    assert type(output) is BoundaryOutputPacket
    assert output.status == ModuleStatus.OK and output.quality_ok
    assert output.target_object_track_id == 7
    assert (output.frame_id, output.timestamp_s) == (4, 4 / 30)
    assert output.centroid_px == pytest.approx((x + 25, y + 25), abs=1)
    assert output.area_px == pytest.approx(2500, abs=15)
    points = np.asarray(output.contour_px)
    assert np.all(points >= (0, 0)) and np.all(points < (160, 120))
    assert points.min(axis=0) == pytest.approx((x, y), abs=1)
    assert points.max(axis=0) == pytest.approx((x + 50, y + 50), abs=1)


@pytest.mark.parametrize("moving", [False, True])
def test_repeated_frame_drops_preserve_real_module03_boundary_confirmation(moving):
    optimizer, boundary = OptimizationSequence(), BoundaryPipeline()
    # Drop packets between Module 03 and Module 04. Module 03's existing policy
    # degrades its own missing-source inputs; this test preserves that policy.
    # Every packet consumed by Module 04 is real, quality-gated evidence.
    for frame_id in range(13):
        frame, objects = scene(frame_id)
        offset = 3 * frame_id if moving else 0
        frame.image[:] = np.roll(frame.image, offset, axis=1)
        objects.detections[0].bbox = BoundingBox(30 + offset, 30, 90 + offset, 90)
        optimized = optimizer.process(objects)
        if frame_id >= 4 and frame_id % 2 == 0:
            assert optimized.quality_ok
            output = boundary.process_optimization(optimized, frame)
    assert output.quality_ok and output.state_confirmed
    assert output.boundary_state == (
        BoundaryState.MOVING if moving else BoundaryState.STATIONARY
    )
