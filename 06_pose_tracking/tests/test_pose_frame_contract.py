"""PoseFrame / HandPose / Landmark contract and landmark topology."""

import json
from dataclasses import FrozenInstanceError, asdict, replace

import pytest
from pose_tracking.contracts import (
    LEFT,
    RIGHT,
    UNKNOWN,
    FrameKey,
    HandPose,
    Landmark,
    PoseContractError,
    PoseFrame,
)
from pose_tracking.landmarks import (
    BODY_CONNECTIONS,
    BODY_LANDMARK_NAMES,
    HAND_CONNECTIONS,
    HAND_LANDMARK_NAMES,
)

from shared.enums.module_status import ModuleStatus


def body(x=100.0):
    return tuple(
        Landmark(i, n, x + i, 50.0 + i, -0.1, 0.9, 0.9)
        for i, n in enumerate(BODY_LANDMARK_NAMES)
    )


def hand_points(x=200.0):
    return tuple(
        Landmark(i, n, x + i, 300.0 + i, 0.0) for i, n in enumerate(HAND_LANDMARK_NAMES)
    )


def test_empty_frame_no_body_no_hands_is_valid():
    frame = PoseFrame(7, 1.25, status=ModuleStatus.NO_DETECTION)
    assert frame.body_landmarks == () and frame.hands == ()
    assert not frame.body_detected and not frame.has_observation
    assert frame.hand(LEFT) is None and frame.body_landmark("nose") is None


def test_one_hand_frame():
    frame = PoseFrame(1, 0.1, hands=(HandPose(RIGHT, hand_points(), 0.97, "Left"),))
    hand = frame.hand(RIGHT)
    assert hand is not None and frame.hand(LEFT) is None
    assert hand.wrist.name == "wrist" and hand.landmark("index_finger_tip").index == 8
    assert hand.model_handedness == "Left"
    assert frame.has_observation and not frame.body_detected


def test_two_hands_and_body():
    frame = PoseFrame(
        2,
        0.2,
        body_landmarks=body(),
        body_detected=True,
        body_score=0.9,
        hands=(HandPose(LEFT, hand_points(10)), HandPose(RIGHT, hand_points(400))),
    )
    assert frame.hand(LEFT).wrist.x == 10 and frame.hand(RIGHT).wrist.x == 400
    assert frame.body_landmark("left_wrist").index == 15
    x1, y1, x2, y2 = frame.hand(LEFT).bbox_xyxy
    assert (x1, y1, x2, y2) == (10, 300, 30, 320)
    cx, _ = frame.hand(LEFT).palm_center
    assert cx == pytest.approx((10 + 15 + 19 + 23 + 27) / 5)


def test_held_hand_is_explicit():
    held = HandPose(LEFT, hand_points(), observed=False, frames_since_seen=2)
    frame = PoseFrame(3, 0.3, hands=(held,))
    assert not frame.has_observation
    with pytest.raises(PoseContractError):
        HandPose(LEFT, hand_points(), observed=True, frames_since_seen=1)
    with pytest.raises(PoseContractError):
        HandPose(LEFT, hand_points(), observed=False, frames_since_seen=0)


def test_held_body_is_not_detected():
    frame = PoseFrame(4, 0.4, body_landmarks=body(), body_frames_since_seen=1)
    assert not frame.body_detected and frame.body_landmarks
    with pytest.raises(PoseContractError):
        PoseFrame(
            4, 0.4, body_landmarks=body(), body_detected=True, body_frames_since_seen=1
        )
    with pytest.raises(PoseContractError):
        PoseFrame(
            4, 0.4, body_landmarks=body(), body_detected=False
        )  # observed must say so
    with pytest.raises(PoseContractError):
        PoseFrame(4, 0.4, body_detected=True)
    with pytest.raises(PoseContractError):
        PoseFrame(
            4, 0.4, body_landmarks=body(), body_frames_since_seen=1, body_score=0.5
        )


@pytest.mark.parametrize(
    "kwargs",
    [
        {"frame_id": -1},
        {"frame_id": True},
        {"timestamp_s": float("nan")},
        {"source_id": ""},
        {"session_id": ""},
        {"status": "ok"},
        {"hands": [HandPose(LEFT, hand_points())]},
        {"hands": (HandPose(LEFT, hand_points()), HandPose(LEFT, hand_points(50)))},
        {"body_landmarks": body()[:20], "body_detected": True},
    ],
)
def test_invalid_frames_rejected(kwargs):
    values = {"frame_id": 1, "timestamp_s": 0.5} | kwargs
    with pytest.raises(PoseContractError):
        PoseFrame(**values)


def test_unknown_hands_may_repeat():
    frame = PoseFrame(
        1,
        0.0,
        hands=(HandPose(UNKNOWN, hand_points()), HandPose(UNKNOWN, hand_points(9))),
    )
    assert len(frame.hands) == 2


@pytest.mark.parametrize(
    "landmark",
    [
        lambda: Landmark(0, "wrist", float("inf"), 0.0, 0.0),
        lambda: Landmark(0, "wrist", 0.0, 0.0, 0.0, visibility=1.5),
        lambda: Landmark(0, "wrist", 0.0, 0.0, 0.0, presence=-0.1),
    ],
)
def test_invalid_landmarks_rejected(landmark):
    with pytest.raises(PoseContractError):
        landmark()


def test_hand_requires_21_ordered_landmarks():
    points = hand_points()
    with pytest.raises(PoseContractError):
        HandPose(LEFT, points[:20])
    with pytest.raises(PoseContractError):
        HandPose(LEFT, (points[1],) + points[1:])
    with pytest.raises(PoseContractError):
        HandPose("left", points)
    with pytest.raises(PoseContractError):
        HandPose(LEFT, points, handedness_score=2.0)


def test_frozen_and_serializable():
    frame = PoseFrame(
        5,
        0.5,
        body_landmarks=body(),
        body_detected=True,
        hands=(HandPose(LEFT, hand_points()),),
    )
    with pytest.raises(FrozenInstanceError):
        frame.frame_id = 6
    with pytest.raises(FrozenInstanceError):
        frame.hands[0].landmarks[0].x = 1.0
    data = json.loads(json.dumps(asdict(frame)))
    assert data["frame_id"] == 5 and data["status"] == "ok"
    assert (
        len(data["body_landmarks"]) == 33 and len(data["hands"][0]["landmarks"]) == 21
    )
    assert replace(frame, frame_id=6).frame_id == 6  # replace re-validates


def test_frame_key_carries_source_identity():
    frame = PoseFrame(9, 3.0, source_id="cam", session_id="s1")
    assert frame.key == FrameKey("cam", "s1", 9, 3.0)


def test_topology_tables_are_consistent():
    assert len(BODY_LANDMARK_NAMES) == 33 and len(HAND_LANDMARK_NAMES) == 21
    assert all(0 <= a < 33 and 0 <= b < 33 for a, b in BODY_CONNECTIONS)
    assert all(0 <= a < 21 and 0 <= b < 21 for a, b in HAND_CONNECTIONS)
    assert len(set(BODY_CONNECTIONS)) == len(BODY_CONNECTIONS)
    # every finger joint is connected
    assert {i for edge in HAND_CONNECTIONS for i in edge} == set(range(21))


def test_topology_matches_mediapipe():
    vision = pytest.importorskip("mediapipe.tasks.python.vision")
    ours_body = {frozenset(e) for e in BODY_CONNECTIONS}
    theirs_body = {
        frozenset((c.start, c.end))
        for c in vision.PoseLandmarksConnections.POSE_LANDMARKS
    }
    assert ours_body == theirs_body
    ours_hand = {frozenset(e) for e in HAND_CONNECTIONS}
    theirs_hand = {
        frozenset((c.start, c.end))
        for c in vision.HandLandmarksConnections.HAND_CONNECTIONS
    }
    assert ours_hand == theirs_hand
    assert [lm.name.lower() for lm in vision.PoseLandmark] == list(BODY_LANDMARK_NAMES)
