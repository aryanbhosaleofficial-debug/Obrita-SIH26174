"""Reviewer R01-R09 and break cases against the actual stage/packet chain."""

import json
import socket
import sys
from dataclasses import asdict, replace
from types import SimpleNamespace

import numpy as np
import pytest
from boundary.input.contract_validator import (
    BoundaryInputError,
    validate_boundary_input,
)
from optimization.interaction.associations import associate
from optimization.reference_frame.coordinate_frame import (
    ArucoCoordinateTransformer,
    ManualRackTransformer,
)
from yolo.inference.detector import UltralyticsYoloDetector

from integration.chain import PerceptionChain
from integration.marker_scene import marker_board
from integration.mocks import MockDetector, MockHandTracker
from perception.core import FrameProcessor
from shared.config import DetectorConfig, InteractionConfig
from shared.diagnostics import NoticeCode, WarningCode
from shared.enums.module_status import ModuleStatus
from shared.errors import InitializationError
from shared.schemas.object_frame import DetectedObject, ObjectFrame
from shared.schemas.observations import (
    BoundingBox,
    CoordinateFrame,
    Detection,
    InteractionType,
    Point2D,
    ReferenceSource,
)
from shared.schemas.optimization_packet import OptimizationOutputPacket
from shared.schemas.prepared_frame import PreparedFrame
from shared.utils.observation import combine_confidence


def chain(config, detections, hands, **kwargs):
    return PerceptionChain(
        config,
        detector=MockDetector(detections),
        hand_tracker=MockHandTracker(hands),
        **kwargs,
    )


def test_r01_realistic_capabilities_are_healthy_and_serialized(config, packet, scene):
    d, h = scene
    d[0].track_id = None
    h[0].confidence = None
    h[0].identity_persistent = False
    with chain(config, [d], [h]) as pipeline:
        output = [pipeline.process(packet(i)) for i in range(5)][-1].optimization
    assert output.status == ModuleStatus.OK and output.reliable_for_temporal_reasoning
    codes = {n.code for n in output.notices}
    assert {
        NoticeCode.HAND_CONFIDENCE_UNAVAILABLE,
        NoticeCode.OBJECT_TRACKING_DISABLED,
        NoticeCode.HAND_IDENTITY_NONPERSISTENT,
        NoticeCode.STATIC_REFERENCE,
    } <= codes
    assert output.warnings == []
    wire = json.loads(json.dumps(asdict(output)))
    assert wire["reliable_for_temporal_reasoning"] is True
    assert wire["observations"]["hands"][0]["confidence"] is None
    assert wire["observations"]["reference_frame"]["verified_this_frame"] is False
    assert wire["observations"]["detections"][0]["track_id"] is None
    assert combine_confidence().final is None
    assert combine_confidence(geometry=0).final == 0


@pytest.mark.parametrize("name", ["vial", "tool"])
def test_r02_context_nested_boxes_preserve_interactable(config, packet, scene, name):
    d, h = scene
    d[0].class_name = name
    d.extend(
        [
            Detection(1, "rack", 0.9, BoundingBox(0, 0, 320, 240), 8),
            Detection(2, "experiment_board", 0.9, BoundingBox(80, 40, 240, 200), 9),
        ]
    )
    with chain(config, [d], [h]) as pipeline:
        output = [pipeline.process(packet(i)) for i in range(5)][
            -1
        ].optimization.observations
    assert len(output.associations) == 3
    assert len([a for a in output.associations if a.is_context]) == 2
    assert not output.associations[0].ambiguous
    assert output.interactions and {i.object_class for i in output.interactions} == {
        name
    }


def test_r02_equal_interactables_remain_observable(config, packet, scene):
    d, h = scene
    d.append(replace(d[0], track_id=8, class_name="tool", class_id=1))
    with chain(config, [d], [h]) as pipeline:
        output = [pipeline.process(packet(i)) for i in range(5)][
            -1
        ].optimization.observations
    assert all(a.ambiguous for a in output.associations)
    assert {i.object_id for i in output.interactions} == {"7", "8"}
    assert all(i.ambiguous for i in output.interactions)


def make_hand_at(hand, x):
    return replace(hand, landmarks=[Point2D(x, 120)], palm_center=Point2D(x, 120))


def test_r03_leaving_edge_once_then_rearm(config, packet, scene):
    d, h = scene
    frames = [
        [make_hand_at(h[0], x)]
        for x in [195] * 4 + [240, 260, 280] + [195] * 4 + [240, 260]
    ]
    with chain(config, [d], frames) as pipeline:
        output = [
            pipeline.process(packet(i, timestamp=i * 0.1)).optimization.observations
            for i in range(len(frames))
        ]
    leaving = lambda r: [
        i for i in r.interactions if i.interaction_type == InteractionType.LEAVING
    ]
    assert leaving(output[4]) and leaving(output[11])
    assert all(not leaving(output[i]) for i in (5, 6, 12))
    assert leaving(output[4])[0].event_timestamp_s == pytest.approx(0.4)


def test_r03_no_late_leaving_and_short_missing_tolerated(config, packet, scene):
    d, h = scene
    near, far = [make_hand_at(h[0], 195)], [make_hand_at(h[0], 240)]
    for delay, expected in [(0.2, True), (0.7, False)]:
        with chain(config, [d], [near] * 4 + [[]] + [far]) as pipeline:
            for i in range(4):
                pipeline.process(packet(i, timestamp=i * 0.1))
            pipeline.process(packet(4, timestamp=0.35))
            output = pipeline.process(
                packet(5, timestamp=0.3 + delay)
            ).optimization.observations
        assert (
            bool(
                [
                    i
                    for i in output.interactions
                    if i.interaction_type == InteractionType.LEAVING
                ]
            )
            == expected
        )


@pytest.mark.parametrize("shape", [(300, 600), (600, 300)])
def test_r04_isotropic_fallback_landscape_portrait(scene, shape):
    d, h = scene
    d[0].bbox = BoundingBox(100, 100, 140, 140)
    horizontal = replace(
        h[0], palm_center=Point2D(170, 120), landmarks=[Point2D(170, 120)]
    )
    vertical = replace(
        h[0], palm_center=Point2D(120, 170), landmarks=[Point2D(120, 170)]
    )
    rows = associate([horizontal, vertical], d, shape, InteractionConfig(), False)
    assert rows[0].minimum_landmark_distance == pytest.approx(
        rows[1].minimum_landmark_distance
    )
    assert rows[0].minimum_landmark_distance == pytest.approx(30 / np.hypot(*shape))
    assert all(a.coordinate_frame == CoordinateFrame.IMAGE_DIAGONAL for a in rows)


def test_r04_ninety_degree_fallback_rotation(scene):
    d, h = scene
    d[0].bbox = BoundingBox(100, 100, 140, 140)
    h[0] = replace(h[0], palm_center=Point2D(170, 120), landmarks=[Point2D(170, 120)])
    original = associate(h, d, (300, 600), InteractionConfig(), False)[0]
    # Clockwise rotation: x'=H-y, y'=x.
    d[0].bbox = BoundingBox(160, 100, 200, 140)
    h[0] = replace(h[0], palm_center=Point2D(180, 170), landmarks=[Point2D(180, 170)])
    rotated = associate(h, d, (600, 300), InteractionConfig(), False)[0]
    assert rotated.minimum_landmark_distance == pytest.approx(
        original.minimum_landmark_distance
    )
    assert rotated.near == original.near


def test_r05_hand_reorder_dropout_and_untracked_object(config, packet, scene):
    d, h = scene
    d[0].track_id = None
    left = replace(make_hand_at(h[0], 40), hand_id="hand_0", identity_persistent=False)
    right = replace(
        make_hand_at(h[0], 280), hand_id="hand_1", identity_persistent=False
    )
    frames = [
        [left, right],
        [replace(right, hand_id="hand_0"), replace(left, hand_id="hand_1")],
        [],
        [left, right],
    ]
    with chain(config, [d], frames) as pipeline:
        results = [
            pipeline.process(packet(i)).optimization.observations for i in range(4)
        ]
    assert [h.continuity_key for h in results[0].hands] == list(
        reversed([h.continuity_key for h in results[1].hands])
    )
    assert [h.continuity_key for h in results[0].hands] == [
        h.continuity_key for h in results[3].hands
    ]
    assert all(
        r.detections[0].track_id is None and not r.detections[0].identity_persistent
        for r in results
    )
    assert len({r.detections[0].continuity_key for r in results}) == 1


def test_r05_crossing_ambiguity_does_not_claim_old_identity(config, packet, scene):
    d, h = scene
    frames = []
    for positions in [(120, 180), (145, 155), (150, 150), (190, 110)]:
        frames.append(
            [
                replace(
                    make_hand_at(h[0], x),
                    hand_id=f"hand_{i}",
                    identity_persistent=False,
                )
                for i, x in enumerate(positions)
            ]
        )
    with chain(config, [d], frames) as pipeline:
        results = [
            pipeline.process(packet(i)).optimization.observations for i in range(4)
        ]
    before = {h.continuity_key for h in results[0].hands}
    assert all(h.identity_ambiguous for h in results[1].hands)
    assert all(
        h.continuity_key not in before and not h.identity_persistent
        for h in results[2].hands
    )


def test_r06_static_reference_does_not_claim_live_verification():
    transformer = ManualRackTransformer(
        [[0.1, 0.1], [0.9, 0.1], [0.9, 0.9], [0.1, 0.9]]
    )
    for image in [marker_board(), np.rot90(marker_board()).copy()]:
        info = transformer.update(image)
        assert info.valid and info.source == ReferenceSource.STATIC_MANUAL
        assert not info.verified_this_frame and info.verified_timestamp_s is None


@pytest.mark.parametrize("rotation", [0, 1, 2, 3])
def test_live_aruco_rotations_and_marker_loss(rotation):
    board = np.rot90(marker_board(), rotation).copy()
    transformer = ArucoCoordinateTransformer()
    info = transformer.update(board)
    assert (
        info.valid and info.verified_this_frame and info.source == ReferenceSource.ARUCO
    )
    center = transformer.image_to_reference(Point2D(199.5, 199.5), (400, 400))
    assert (center.x, center.y) == pytest.approx((0.5, 0.5), abs=0.005)
    # An off-center physical point must retain rack coordinates as image axes rotate.
    point = Point2D(139.5, 259.5)
    for _ in range(rotation):
        point = Point2D(point.y, 399 - point.x)
    mapped_point = transformer.image_to_reference(point, (400, 400))
    assert (mapped_point.x, mapped_point.y) == pytest.approx((0.25, 0.75), abs=1e-5)
    for actual, expected in zip(info.axes_pixels, [(0, 0), (1, 0), (0, 1)]):
        mapped = transformer.image_to_reference(actual, (400, 400))
        assert (mapped.x, mapped.y) == pytest.approx(expected, abs=1e-5)
    lost = transformer.update(np.full_like(board, 255))
    assert not lost.valid and not lost.verified_this_frame
    with pytest.raises(ValueError):
        transformer.image_to_reference(Point2D(200, 200), (400, 400))


def test_r07_rates_equal_at_different_fps(config, packet, scene):
    d, h = scene
    rates = []
    for dt in [0.025, 0.1]:
        frames = [[make_hand_at(h[0], 205 + 32 * i * dt)] for i in range(5)]
        with chain(config, [d], frames) as pipeline:
            observations = [
                pipeline.process(packet(i, timestamp=i * dt)).optimization.observations
                for i in range(5)
            ]
        rates.append(observations[-1].associations[0].distance_rate_per_s)
    assert rates == pytest.approx([0.1, 0.1], abs=1e-5)  # 32 pixels/s / 320 rack width


def test_r08_malformed_frame_ages_without_reset(config, packet, scene):
    with chain(config, [scene[0]], [scene[1]]) as pipeline:
        for i in range(4):
            output = pipeline.process(packet(i))
        old_key = output.optimization.observations.hands[0].continuity_key
        malformed = pipeline.process(replace(packet(4), image=None))
        assert malformed.optimization.status == ModuleStatus.INVALID_INPUT
        assert all(
            w.code != WarningCode.TEMPORAL_HISTORY_RESET
            for w in malformed.optimization.warnings
        )
        recovered = pipeline.process(packet(5)).optimization.observations
        assert recovered.detections[0].is_stable and recovered.interactions
        assert recovered.hands[0].continuity_key == old_key
        pipeline.reset()
        new = pipeline.process(
            replace(packet(0), session_id="new_session")
        ).optimization.observations
        assert not new.detections[0].is_stable


def test_r09_numpy_integer_frame_id_and_real_foundation_contract(packet):
    result = FrameProcessor().process(replace(packet(), frame_id=np.int64(0)))
    assert isinstance(result, PreparedFrame) and result.status == ModuleStatus.OK
    assert type(result.source.frame_id) is int
    assert not hasattr(result, "detections")  # Module 01 cannot run inference.


def test_authoritative_chain_packets_and_boundary_rejects_mix(config, packet, scene):
    with chain(config, [scene[0]], [scene[1]]) as pipeline:
        for i in range(5):
            result = pipeline.process(packet(i))
    assert isinstance(result.prepared, PreparedFrame) and isinstance(
        result.objects, ObjectFrame
    )
    assert isinstance(result.optimization, OptimizationOutputPacket)
    assert DetectedObject is Detection
    validate_boundary_input(result.optimization, result.prepared.source)
    with pytest.raises(BoundaryInputError, match="metadata"):
        validate_boundary_input(result.optimization, packet(99))
    result.optimization.observations.associations[
        0
    ].coordinate_frame = CoordinateFrame.IMAGE_PIXELS
    with pytest.raises(BoundaryInputError, match="mixed coordinate"):
        validate_boundary_input(result.optimization, result.prepared.source)


def test_offline_chain_reuses_models_and_preserves_source(
    config, packet, scene, monkeypatch
):
    monkeypatch.setattr(
        socket.socket,
        "connect",
        lambda *args: pytest.fail("network request during offline chain"),
    )

    class CountDetector(MockDetector):
        initializations = 0

        def initialize(self):
            self.initializations += 1
            super().initialize()

    detector = CountDetector([scene[0]])
    source = packet()
    original = source.image.copy()
    with PerceptionChain(
        config, detector=detector, hand_tracker=MockHandTracker([scene[1]])
    ) as pipeline:
        for i in range(8):
            pipeline.process(replace(source, frame_id=i, timestamp_s=i / 30))
    assert detector.initializations == 1 and np.array_equal(original, source.image)


def test_wrong_model_classes_fail_every_initialization_attempt(monkeypatch, tmp_path):
    model = tmp_path / "test.pt"
    model.touch()
    classes = tmp_path / "classes.yaml"
    classes.write_text("classes: [{id: 0, name: vial}]")
    monkeypatch.setitem(
        sys.modules,
        "torch",
        SimpleNamespace(
            cuda=SimpleNamespace(is_available=lambda: False), backends=SimpleNamespace()
        ),
    )
    monkeypatch.setitem(
        sys.modules,
        "ultralytics",
        SimpleNamespace(YOLO=lambda *a, **k: SimpleNamespace(names={0: "wrong"})),
    )
    monkeypatch.setitem(
        sys.modules,
        "ultralytics.utils",
        SimpleNamespace(checks=SimpleNamespace(AUTOINSTALL=False)),
    )
    detector = UltralyticsYoloDetector(
        DetectorConfig(model_path=model, classes_path=classes)
    )
    for _ in range(2):
        with pytest.raises(InitializationError, match="incompatible"):
            detector.initialize()


def test_different_unit_thresholds_are_not_reused(scene):
    d, h = scene
    h[0] = make_hand_at(h[0], 230)
    thresholds = InteractionConfig()
    thresholds.image_diagonal.proximity_threshold = 0.01
    thresholds.image_diagonal.contact_threshold = 0.005
    fallback = associate(h, d, (240, 320), thresholds, False)[0]
    assert not fallback.near
    d[0].reference_polygon = tuple(
        Point2D(p.x / 320, p.y / 240) for p in d[0].bbox.corners
    )
    h[0].reference_palm_center = Point2D(230 / 320, 0.5)
    h[0].reference_landmarks = [h[0].reference_palm_center]
    thresholds.rack_relative.proximity_threshold = 0.15
    rack = associate(h, d, (240, 320), thresholds, True)[0]
    assert rack.near and rack.distance_units == "rack_units"
