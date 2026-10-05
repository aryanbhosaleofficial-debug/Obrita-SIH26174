"""Validity, coordinates, geometry and temporal regressions without model files."""
from dataclasses import replace

import numpy as np
import pytest

from pose_tracking.contracts import Landmark, PoseFrame, UNKNOWN
from pose_tracking.geometry import hand_bbox, normalize_landmarks, reference_matrix
from pose_tracking.sync import to_hand_observations, to_pose_observation
from shared.enums.module_status import ModuleStatus
from shared.schemas.observations import CoordinateFrame, ReferenceFrameInfo


def rack(matrix):
    return ReferenceFrameInfo(valid=True, reference_id="rack-test",
                              image_to_reference_matrix=tuple(map(tuple, matrix)))


def test_metadata_and_coordinate_representations(frames, make_tracker, raw):
    tracker, backend = make_tracker([raw.result(raw.body(), (raw.hand(),))])
    prepared = frames(640, 480, max_width=320)()
    prepared.source.metadata["experiment"] = {"id": "BAS"}
    workspace = rack([[1 / 640, 0, 0], [0, 1 / 480, 0], [0, 0, 1]])
    output = tracker.process(prepared, workspace=workspace)
    assert isinstance(output, PoseFrame) and backend.calls == 1
    assert output.feature_coordinate_frame == CoordinateFrame.RACK_RELATIVE
    assert output.coordinate_frame == CoordinateFrame.IMAGE_PIXELS
    assert output.reference_id == "rack-test" and output.inference_ms >= 0
    for point in output.body_landmarks + output.hands[0].landmarks:
        assert point.normalized_xy == pytest.approx((point.x / 640, point.y / 480))
        assert point.rack_xy == pytest.approx(point.normalized_xy)
    prepared.source.metadata["experiment"]["id"] = "changed"
    assert output.metadata["experiment"]["id"] == "BAS"
    observation = to_hand_observations(output)[0]
    assert len(observation.reference_landmarks) == 21
    assert observation.reference_palm_center is not None
    assert len(to_pose_observation(output).reference_landmarks) == 33


@pytest.mark.parametrize("degrees", [0, 90, 180])
def test_rack_representation_is_rotation_equivariant(degrees):
    # Supplied calibration rotates with the setup. Module 06 never infers up.
    angle = np.radians(degrees)
    rotation = np.array([[np.cos(angle), -np.sin(angle), 120],
                         [np.sin(angle), np.cos(angle), 80], [0, 0, 1]])
    original = np.array([40.0, 70.0, 1.0])
    rotated = rotation @ original
    image_to_rack = np.diag([1 / 200, 1 / 200, 1]) @ np.linalg.inv(rotation)
    point = Landmark(0, "wrist", rotated[0], rotated[1], -.3)
    mapped = normalize_landmarks((point,), 320, 240,
                                 reference_matrix(rack(image_to_rack)))[0]
    assert mapped.rack_xy == pytest.approx((.2, .35))
    assert mapped.z == -.3  # planar calibration must not manufacture depth


def test_camera_fallback_and_invalid_reference(frames, make_tracker, raw):
    tracker, backend = make_tracker([raw.result(raw.body())])
    make = frames()
    prepared = make()
    invalid = rack([[0, 0, 0], [0, 0, 0], [0, 0, 0]])
    assert tracker.process(prepared, workspace=invalid).status == ModuleStatus.INVALID_INPUT
    assert backend.calls == 0
    # Reference validation did not consume the source cursor.
    result = tracker.process(prepared, workspace=ReferenceFrameInfo(valid=False))
    assert result.feature_coordinate_frame == CoordinateFrame.NORMALIZED_IMAGE
    assert result.body_landmarks[0].rack_xy is None


def test_homography_horizon_is_explicitly_invalid():
    points = (Landmark(0, "wrist", 0, 30, 0),)
    transformed = normalize_landmarks(points, 100, 100,
                                     np.array([[0, 0, 1], [0, 1, 0], [1, 0, 0]]))[0]
    assert not transformed.is_valid and transformed.rack_xy is None


@pytest.mark.parametrize("matrix", [None, [[1, 0], [0, 1]],
                                     [[1, 0, 0], [0, 1, 0], [0, 0, float("nan")]]])
def test_malformed_valid_reference_rejected(matrix):
    with pytest.raises(ValueError):
        reference_matrix(ReferenceFrameInfo(valid=True, image_to_reference_matrix=matrix))


def test_bbox_padding_clamping_and_invalid_joints():
    points = (Landmark(0, "wrist", -10, 20, 0),
              Landmark(1, "thumb_cmc", 150, 90, 0),
              Landmark(2, "thumb_mcp", 10000, 10000, 0, is_valid=False))
    assert hand_bbox(points, 100, 80, .1) == (0, 12, 100, 80)
    assert hand_bbox(tuple(replace(p, is_valid=False) for p in points), 100, 80) is None
    assert hand_bbox((Landmark(0, "wrist", 200, 200, 0),), 100, 80) is None
    with pytest.raises(ValueError):
        hand_bbox(points, 0, 80)
    with pytest.raises(ValueError):
        normalize_landmarks(points, 100, 0)


def test_low_visibility_joint_never_becomes_a_valid_smoothed_joint(frames, make_tracker, raw):
    first = raw.body()
    low = (replace(first[0], x=.7, visibility=.1),) + first[1:]
    recovered = (replace(first[0], x=.6),) + first[1:]
    tracker, _ = make_tracker([raw.result(first), raw.result(low), raw.result(recovered)],
                              smoothing_alpha=.5)
    make = frames()
    tracker.process(make())
    result = tracker.process(make())
    assert result.body_detected and not result.body_landmarks[0].is_valid
    assert to_pose_observation(result) is None  # legacy contract cannot retain a validity mask
    result = tracker.process(make())
    assert result.body_landmarks[0].is_valid
    assert result.body_landmarks[0].x == pytest.approx(.6 * 640)  # no EMA of bad history


def test_all_low_visibility_is_not_a_fresh_pose(frames, make_tracker, raw):
    tracker, _ = make_tracker([raw.result(raw.body(visibility=.1))])
    result = tracker.process(frames()())
    assert not result.body_detected and not result.has_observation


@pytest.mark.parametrize("score", [.1, None, float("nan"), True])
def test_uncertain_handedness_is_unknown_not_a_fabricated_side(frames, make_tracker, raw, score):
    tracker, _ = make_tracker([raw.result(hands=(raw.hand(score=score),))])
    output = tracker.process(frames()())
    assert output.hands[0].handedness == UNKNOWN
    assert not output.left_hand_detected and not output.right_hand_detected
    assert output.hands[0].landmarks[0].visibility is None
    assert output.hands[0].bbox is not None  # label ambiguity doesn't erase usable geometry


def test_invalid_hand_joint_is_not_exported_as_trusted_legacy_observation(frames, make_tracker, raw):
    hand = raw.hand()
    points = (replace(hand.landmarks[0], presence=.1),) + hand.landmarks[1:]
    tracker, _ = make_tracker([raw.result(hands=(replace(hand, landmarks=points),))])
    output = tracker.process(frames()())
    assert not output.hands[0].wrist.is_valid and output.hands[0].palm_center is None
    assert to_hand_observations(output) == []


def test_consecutive_counts_and_loss_recovery(frames, make_tracker, raw):
    observed = raw.result(raw.body(), (raw.hand(),))
    tracker, _ = make_tracker([observed, observed, raw.result(), observed])
    make = frames()
    results = [tracker.process(make()) for _ in range(4)]
    assert [p.body_consecutive_frames for p in results] == [1, 2, 0, 1]
    assert [p.hands[0].consecutive_frames for p in results] == [1, 2, 0, 1]
    assert results[2].body_frames_since_seen == 1 and not results[2].hands[0].observed


def test_failure_clears_stale_smoothing_before_recovery(frames, make_tracker, raw):
    tracker, _ = make_tracker([raw.result(raw.body(cx=.4)), RuntimeError("failed"),
                              raw.result(raw.body(cx=.45))], smoothing_alpha=.5)
    make = frames()
    tracker.process(make())
    assert tracker.process(make()).status == ModuleStatus.ERROR
    recovered = tracker.process(make())
    assert recovered.body_consecutive_frames == 1
    assert recovered.body_landmarks[0].x == pytest.approx((.45 - .012) * 640)


@pytest.mark.parametrize("image", [None, np.empty((0, 0, 3), np.uint8),
                                  np.zeros((2, 2, 5), np.uint8), "unsupported"])
def test_invalid_frame_images_skip_inference(frames, make_tracker, image):
    factory = frames()
    packet = factory.packet()
    packet.image = image
    tracker, backend = make_tracker()
    result = tracker.process(factory.core.process(packet))
    assert result.frame_id == packet.frame_id and result.timestamp_s == packet.timestamp_s
    assert result.status == ModuleStatus.INVALID_INPUT and backend.calls == 0
