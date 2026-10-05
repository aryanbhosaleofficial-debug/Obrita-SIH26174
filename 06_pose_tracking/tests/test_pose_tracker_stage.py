"""PreparedFrame -> PoseFrame stage behaviour with a scripted (model-free) backend."""

from pathlib import Path

import pytest
from pose_tracking.backends import MediaPipeLandmarkBackend
from pose_tracking.contracts import LEFT, RIGHT, UNKNOWN
from pose_tracking.tracker import PoseHandTracker

from shared.diagnostics import WarningCode
from shared.enums.module_status import ModuleStatus
from shared.errors import InitializationError


def codes(frame):
    return {w.code for w in frame.warnings}


def test_metadata_preserved_from_input_frame(frames, make_tracker, raw):
    make = frames(source_id="cam-7", session_id="run-3")
    tracker, _ = make_tracker([raw.result(raw.body())])
    for frame_id, ts in ((4, 10.5), (9, 10.75), (10, 11.0)):
        prepared = make(frame_id, ts)
        pose = tracker.process(prepared)
        src = prepared.source
        assert (pose.frame_id, pose.timestamp_s) == (src.frame_id, src.timestamp_s)
        assert (pose.source_id, pose.session_id) == ("cam-7", "run-3")
        assert (pose.image_width, pose.image_height) == (640, 480)


def test_no_body_no_hands_is_no_detection(frames, make_tracker):
    tracker, backend = make_tracker()
    pose = tracker.process(frames()())
    assert pose.status == ModuleStatus.NO_DETECTION
    assert pose.body_landmarks == () and pose.hands == () and not pose.body_detected
    assert backend.calls == 1


def test_body_landmarks_in_source_pixels(frames, make_tracker, raw):
    tracker, _ = make_tracker([raw.result(raw.body(cx=0.5, cy=0.5))])
    pose = tracker.process(frames()())
    assert pose.status == ModuleStatus.OK and pose.body_detected
    nose = pose.body_landmark("nose")
    assert nose.x == pytest.approx((0.5 - 0.012) * 640)
    assert nose.y == pytest.approx((0.5 - 0.012) * 480)
    assert pose.body_score == pytest.approx(0.9)


def test_resized_prepared_image_still_maps_to_source_pixels(frames, make_tracker, raw):
    make = frames(1280, 720, max_width=320)  # Module 01 downsizes for inference
    tracker, _ = make_tracker([raw.result(raw.body(cx=0.5, cy=0.5))])
    prepared = make()
    assert prepared.image.shape[1] == 320
    pose = tracker.process(prepared)
    assert pose.body_landmark("nose").x == pytest.approx((0.5 - 0.012) * 1280)
    assert (pose.image_width, pose.image_height) == (1280, 720)


def test_one_hand_with_default_mirror_convention(frames, make_tracker, raw):
    # Current Tasks bundle reports anatomical sides on unmirrored input.
    tracker, _ = make_tracker([raw.result(hands=(raw.hand("Left"),))])
    pose = tracker.process(frames()())
    assert [h.handedness for h in pose.hands] == [LEFT]
    assert pose.hands[0].model_handedness == "Left"
    assert pose.status == ModuleStatus.OK and not pose.body_detected


@pytest.mark.parametrize(
    ("overrides", "expected"),
    [
        ({"input_mirrored": True}, RIGHT),
        ({"swap_handedness": False}, LEFT),
        ({"input_mirrored": True, "swap_handedness": True}, RIGHT),
    ],
)
def test_handedness_configuration(frames, make_tracker, raw, overrides, expected):
    tracker, _ = make_tracker([raw.result(hands=(raw.hand("Left"),))], **overrides)
    assert tracker.process(frames()()).hands[0].handedness == expected


def test_two_hands_are_independent(frames, make_tracker, raw):
    both = raw.result(hands=(raw.hand("Left", cx=0.2), raw.hand("Right", cx=0.7)))
    right_only = raw.result(hands=(raw.hand("Right", cx=0.7),))
    tracker, _ = make_tracker([both, right_only, right_only, right_only, both])
    make = frames()
    first = tracker.process(make())
    assert [h.handedness for h in first.hands] == [LEFT, RIGHT]
    left_x = first.hand(LEFT).wrist.x
    right_x = first.hand(RIGHT).wrist.x
    assert left_x == pytest.approx(0.2 * 640) and right_x == pytest.approx(0.7 * 640)

    held1 = tracker.process(make())
    assert held1.hand(RIGHT).observed and held1.hand(RIGHT).wrist.x == right_x
    assert not held1.hand(LEFT).observed and held1.hand(LEFT).frames_since_seen == 1
    held2 = tracker.process(make())
    assert held2.hand(LEFT).frames_since_seen == 2
    gone = tracker.process(make())  # beyond max_hold_frames=2
    assert gone.hand(LEFT) is None and gone.hand(RIGHT).observed
    back = tracker.process(make())  # returning hand recovers immediately
    assert back.hand(LEFT).observed and back.hand(RIGHT).observed


def test_zero_one_two_hand_sequence_never_fails(frames, make_tracker, raw):
    sequence = [
        raw.result(),
        raw.result(hands=(raw.hand("Left"),)),
        raw.result(hands=(raw.hand("Left"), raw.hand("Right", cx=0.8))),
        raw.result(),
        raw.result(),
        raw.result(),
    ]
    tracker, _ = make_tracker(sequence, max_hold_frames=0)
    make = frames()
    counts = [len(tracker.process(make()).hands) for _ in sequence]
    assert counts == [0, 1, 2, 0, 0, 0]


def test_duplicate_model_labels_resolved(frames, make_tracker, raw):
    dup = raw.result(
        hands=(raw.hand("Left", cx=0.2, score=0.6), raw.hand("Left", cx=0.7, score=0.9))
    )
    tracker, _ = make_tracker([dup])
    pose = tracker.process(frames()())
    assert [h.handedness for h in pose.hands] == [LEFT, UNKNOWN]
    assert pose.hand(LEFT).handedness_score == 0.9


def test_person_leaving_and_returning(frames, make_tracker, raw):
    seq = [raw.result(raw.body())] + [raw.result()] * 3 + [raw.result(raw.body())]
    tracker, _ = make_tracker(seq)
    make = frames()
    out = [tracker.process(make()) for _ in seq]
    assert out[0].body_detected
    assert (
        not out[1].body_detected
        and out[1].body_frames_since_seen == 1
        and out[1].body_landmarks
    )
    assert out[1].status == ModuleStatus.NO_DETECTION  # held data is not an observation
    assert out[2].body_frames_since_seen == 2
    assert out[3].body_landmarks == ()
    assert out[4].body_detected


def test_backend_failure_is_isolated_to_one_frame(frames, make_tracker, raw):
    tracker, _ = make_tracker(
        [raw.result(raw.body()), RuntimeError("boom"), raw.result(raw.body())]
    )
    make = frames()
    assert tracker.process(make()).status == ModuleStatus.OK
    failed = tracker.process(make())
    assert failed.status == ModuleStatus.ERROR and failed.body_landmarks == ()
    assert WarningCode.POSE_TRACKER_FAILURE in codes(failed)
    assert tracker.process(make()).status == ModuleStatus.OK


def test_rejected_upstream_frame_skips_inference(frames, make_tracker):
    tracker, backend = make_tracker()
    make = frames()
    make(5, 1.0)  # Module 01 has now seen frame 5
    tracker.process(make.core.process(make.packet(6, 1.1)))
    stale = make.core.process(
        make.packet(3, 0.5)
    )  # non-monotonic -> rejected by Module 01
    assert not stale.accepted
    pose = tracker.process(stale)
    assert pose.status == ModuleStatus.INVALID_INPUT and pose.frame_id == 3
    assert backend.calls == 1


def test_non_monotonic_and_source_change_rejected(frames, make_tracker):
    tracker, backend = make_tracker()
    tracker.process(frames()(5, 1.0))
    again = tracker.process(frames()(5, 1.0))  # fresh Module 01, same id at the tracker
    assert again.status == ModuleStatus.INVALID_INPUT
    assert WarningCode.NON_MONOTONIC_FRAME in codes(again)
    other = tracker.process(frames(source_id="other")(9, 2.0))
    assert (
        other.status == ModuleStatus.INVALID_INPUT
        and WarningCode.SOURCE_CHANGED in codes(other)
    )
    tracker.reset()
    assert (
        tracker.process(frames(source_id="other")(0, 0.0)).status
        == ModuleStatus.NO_DETECTION
    )
    assert backend.calls == 2


def test_reset_clears_state_and_model_tracking(frames, make_tracker, raw):
    tracker, backend = make_tracker(
        [raw.result(raw.body(), (raw.hand("Left"),)), raw.result()]
    )
    make = frames()
    tracker.process(make())
    assert tracker.stabilizer.state_size == 2
    tracker.reset()
    assert tracker.stabilizer.state_size == 0
    assert (
        backend.closes == 1 and backend.initializations == 2
    )  # model tracking restarted
    after = tracker.process(make())
    assert (
        after.body_landmarks == () and after.hands == ()
    )  # nothing held from before reset


def test_upstream_temporal_reset_clears_hold(frames, make_tracker, raw):
    tracker, _ = make_tracker([raw.result(raw.body()), raw.result()])
    make = frames()
    tracker.process(make(0, 0.0))
    late = make(1, 5.0)  # > Module 01 max_time_gap_s -> reset_required
    assert late.reset_required
    pose = tracker.process(late)
    assert pose.body_landmarks == () and WarningCode.TEMPORAL_HISTORY_RESET in codes(
        pose
    )


def test_models_load_once(frames, make_tracker, raw):
    tracker, backend = make_tracker([raw.result(raw.body())])
    make = frames()
    for _ in range(50):
        tracker.process(make())
    assert backend.initializations == 1 and backend.calls == 50


def test_partial_model_availability_is_degraded(frames, make_tracker, raw):
    tracker, _ = make_tracker([raw.result(hands=(raw.hand(),), body_available=False)])
    pose = tracker.process(frames()())
    assert pose.status == ModuleStatus.DEGRADED and len(pose.hands) == 1
    assert WarningCode.POSE_TRACKER_FAILURE in codes(pose)


def test_disabled_body_ignores_body_output(frames, make_tracker, raw):
    tracker, _ = make_tracker(
        [raw.result(raw.body(), body_available=False)], body_enabled=False
    )
    pose = tracker.process(frames()())
    assert pose.body_landmarks == () and pose.status == ModuleStatus.NO_DETECTION


def test_invalid_model_output_is_dropped_not_raised(frames, make_tracker, raw):
    bad = raw.body()[:32] + (raw.body()[0].__class__(float("nan"), 0.5, 0.0),)
    tracker, _ = make_tracker([raw.result(bad)])
    pose = tracker.process(frames()())
    assert pose.body_landmarks == () and pose.status == ModuleStatus.DEGRADED
    assert WarningCode.INVALID_OBSERVATION in codes(pose)


def test_type_contract(make_tracker):
    tracker, _ = make_tracker()
    with pytest.raises(TypeError):
        tracker.process(object())


def test_missing_models_fail_initialization_cleanly(config):
    cfg = config(
        pose_model_path=Path("missing/pose.task"),
        hand_model_path=Path("missing/hand.task"),
    )
    tracker = PoseHandTracker(cfg, MediaPipeLandmarkBackend(cfg))
    with pytest.raises(InitializationError, match="model"):
        tracker.initialize()


def test_module01_diagnostics_are_carried_through(frames, make_tracker, raw):
    tracker, _ = make_tracker([raw.result(raw.body())])
    make = frames()
    tracker.process(make(0, 0.0))
    gap = tracker.process(make(3, 0.1))  # frames 1-2 never arrived
    assert gap.status == ModuleStatus.DEGRADED and gap.body_detected
    assert WarningCode.SOURCE_FRAME_MISSING in codes(gap)
    rejected = tracker.process(make.core.process(make.packet(4, 0.1)))  # same timestamp
    assert rejected.status == ModuleStatus.INVALID_INPUT
    assert WarningCode.NON_MONOTONIC_FRAME in codes(rejected)
