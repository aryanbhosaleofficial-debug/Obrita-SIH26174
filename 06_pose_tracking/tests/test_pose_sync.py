"""Same PreparedFrame -> ObjectFrame (real Module 02 stage) and PoseFrame stay pairable."""

import pytest
from pose_tracking.contracts import LEFT, RIGHT
from pose_tracking.sync import (
    FrameSyncError,
    frame_key,
    is_synchronized,
    pair_with_objects,
    require_synchronized,
    to_hand_observations,
    to_pose_observation,
)
from yolo.pipeline import YoloPipeline
from yolo.semantic.contracts import SemanticConfig

from integration.mocks import MockDetector
from shared.config import DetectorConfig
from shared.schemas.object_frame import ObjectFrame
from shared.schemas.observations import (
    BoundingBox,
    Detection,
    HandObservation,
    PoseObservation,
)


@pytest.fixture
def yolo():
    detector = MockDetector(
        [[Detection(2, "blue_tube", 0.8, BoundingBox(20, 10, 60, 50), 12)]]
    )
    pipeline = YoloPipeline(
        DetectorConfig(backend="mock"),
        detector=detector,
        semantic_config=SemanticConfig(enabled=False),
    )
    pipeline.initialize()
    yield pipeline
    pipeline.close()


def test_object_and_pose_branches_share_frame_identity(frames, make_tracker, raw, yolo):
    make = frames(640, 480, max_width=320, source_id="cam-0", session_id="bas-1")
    tracker, _ = make_tracker([raw.result(raw.body(), (raw.hand("Left"),))])
    for frame_id in (0, 1, 3, 7):  # includes ID gaps (dropped frames)
        prepared = make(frame_id, frame_id / 30)
        objects = yolo.process(prepared)
        pose = tracker.process(prepared)
        assert isinstance(objects, ObjectFrame)
        assert objects.frame_id == pose.frame_id == prepared.source.frame_id == frame_id
        assert objects.timestamp_s == pose.timestamp_s == prepared.source.timestamp_s
        assert frame_key(prepared) == frame_key(objects) == frame_key(pose)
        assert is_synchronized(prepared, objects, pose)
        assert pair_with_objects(pose, objects) == (pose, objects)
        assert objects.detections and objects.detections[0].track_id == 12


def test_mismatched_frames_are_rejected(frames, make_tracker, yolo):
    make = frames()
    tracker, _ = make_tracker()
    first = make()
    objects = yolo.process(first)
    pose_next = tracker.process(make())
    assert not is_synchronized(objects, pose_next)
    with pytest.raises(FrameSyncError):
        require_synchronized(objects, pose_next)
    with pytest.raises(FrameSyncError):
        pair_with_objects(pose_next, objects)


def test_frame_key_includes_source_and_session():
    a = ObjectFrame(1, 0.5, 10, 10, source_id="a")
    b = ObjectFrame(1, 0.5, 10, 10, source_id="b")
    assert not is_synchronized(a, b)


def test_adapters_to_existing_shared_observations(frames, make_tracker, raw):
    tracker, _ = make_tracker(
        [
            raw.result(
                raw.body(), (raw.hand("Left", cx=0.2), raw.hand("Right", cx=0.7))
            ),
            raw.result(),
        ]
    )
    make = frames()
    pose = tracker.process(make())
    observation = to_pose_observation(pose)
    assert isinstance(observation, PoseObservation) and len(observation.landmarks) == 33
    assert observation.landmarks[0].x == pose.body_landmarks[0].x
    hands = to_hand_observations(pose)
    assert all(isinstance(h, HandObservation) for h in hands)
    assert [h.handedness for h in hands] == ["Left", "Right"]
    assert not any(h.identity_persistent for h in hands)
    assert hands[0].palm_center.x == pytest.approx(pose.hand(LEFT).palm_center[0])

    held = tracker.process(make())  # everything lost -> held only
    assert held.hand(RIGHT) is not None and not held.hand(RIGHT).observed
    assert to_pose_observation(held) is None and to_hand_observations(held) == []
    assert len(to_hand_observations(held, include_held=True)) == 2
    assert to_pose_observation(held, include_held=True) is not None
