"""Smoothing / hold state: EMA arithmetic, jump reset, bounded memory, reset."""

import sys

import pytest
from pose_tracking.contracts import LEFT, RIGHT, Landmark
from pose_tracking.landmarks import BODY_LANDMARK_NAMES, HAND_LANDMARK_NAMES
from pose_tracking.smoothing import HandCandidate, LandmarkStabilizer

DIAG = 800.0


def body(x):
    return tuple(
        Landmark(i, n, x, 100.0, 0.0, 0.9) for i, n in enumerate(BODY_LANDMARK_NAMES)
    )


def hand(side, x):
    return HandCandidate(
        side,
        tuple(Landmark(i, n, x, 200.0, 0.0) for i, n in enumerate(HAND_LANDMARK_NAMES)),
    )


def test_alpha_one_is_passthrough(config):
    s = LandmarkStabilizer(config(smoothing_alpha=1.0))
    s.update(0, 0.0, DIAG, body(100), [])
    out, since, _ = s.update(1, 0.03, DIAG, body(110), [])
    assert out[0].x == 110 and since == 0


def test_ema_blends_consecutive_observations(config):
    s = LandmarkStabilizer(config(smoothing_alpha=0.5))
    s.update(0, 0.0, DIAG, body(100), [hand(LEFT, 300)])
    out, _, hands = s.update(1, 0.03, DIAG, body(110), [hand(LEFT, 320)])
    assert out[0].x == pytest.approx(105) and hands[0].wrist.x == pytest.approx(310)
    out, _, _ = s.update(2, 0.06, DIAG, body(110), [])
    assert out[0].x == pytest.approx(107.5)


def test_large_jump_restarts_instead_of_blending(config):
    s = LandmarkStabilizer(config(smoothing_alpha=0.5, jump_reset_fraction=0.1))
    s.update(0, 0.0, DIAG, body(100), [])
    out, _, _ = s.update(1, 0.03, DIAG, body(400), [])  # 300 px > 0.1 * 800
    assert out[0].x == 400


def test_hold_is_marked_and_expires(config):
    s = LandmarkStabilizer(config(max_hold_frames=1))
    s.update(0, 0.0, DIAG, body(100), [hand(RIGHT, 50)])
    out, since, hands = s.update(1, 0.03, DIAG, None, [])
    assert (
        out and since == 1 and not hands[0].observed and hands[0].frames_since_seen == 1
    )
    out, since, hands = s.update(2, 0.06, DIAG, None, [])
    assert out == () and since == 0 and hands == () and s.state_size == 0


def test_frame_id_gap_counts_as_missing(config):
    s = LandmarkStabilizer(config(max_hold_frames=2))
    s.update(0, 0.0, DIAG, body(100), [])
    out, _, _ = s.update(5, 0.2, DIAG, None, [])  # 5 frames missing > hold
    assert out == ()


def test_time_gap_clears_state(config):
    s = LandmarkStabilizer(config(max_time_gap_s=0.5, max_hold_frames=5))
    s.update(0, 0.0, DIAG, body(100), [hand(LEFT, 1)])
    out, _, hands = s.update(1, 2.0, DIAG, None, [])
    assert out == () and hands == ()


def test_reset_clears_everything(config):
    s = LandmarkStabilizer(config(max_hold_frames=5))
    s.update(0, 0.0, DIAG, body(100), [hand(LEFT, 1), hand(RIGHT, 2)])
    assert s.state_size == 3
    s.reset()
    assert s.state_size == 0
    out, _, hands = s.update(1, 0.03, DIAG, None, [])
    assert out == () and hands == ()


def test_state_is_bounded_over_long_streams(config):
    s = LandmarkStabilizer(config(smoothing_alpha=0.6, max_hold_frames=3))
    sizes = set()
    for i in range(5000):
        hands = [hand(LEFT, i % 50)] if i % 3 else [hand(RIGHT, i % 70), hand(LEFT, 5)]
        s.update(i, i / 30, DIAG, body(i % 90) if i % 7 else None, hands)
        sizes.add(s.state_size)
    assert max(sizes) <= 3
    assert sys.getsizeof(s.__dict__) < 2048 and set(vars(s)) == {
        "alpha",
        "max_hold_frames",
        "jump_reset_fraction",
        "max_time_gap_s",
        "_body",
        "_hands",
        "_last_timestamp_s",
    }
    assert len(s._hands) <= 2


def test_tracker_holds_no_frame_history(frames, make_tracker, raw):
    tracker, _ = make_tracker(
        [raw.result(raw.body(), (raw.hand("Left"), raw.hand("Right")))]
    )
    make = frames()
    for _ in range(300):
        tracker.process(make())
    # Only scalars, config, lock, backend and the constant-size stabilizer.
    assert not any(
        isinstance(v, (list, dict, tuple, set)) and len(v) > 3
        for v in vars(tracker).values()
    )
    assert tracker.stabilizer.state_size == 3


@pytest.mark.parametrize("reverse_order", [False, True])
def test_nearby_label_swap_never_cross_blends_physical_hands(config, reverse_order):
    s = LandmarkStabilizer(config(smoothing_alpha=.7))
    s.update(0, 0., DIAG, None, [hand(LEFT, 256), hand(RIGHT, 320)])
    swapped = [hand(LEFT, 320), hand(RIGHT, 256)]
    if reverse_order:
        swapped.reverse()
    _, _, hands = s.update(1, .03, DIAG, None, swapped)
    positions = {h.handedness: h.wrist.x for h in hands}
    assert positions == {LEFT: 320, RIGHT: 256}
    assert all(h.consecutive_frames == 1 for h in hands)
    # Labels can recover next frame without blending either opposite track.
    _, _, recovered = s.update(2, .06, DIAG, None, [hand(LEFT, 256), hand(RIGHT, 320)])
    assert {h.handedness: h.wrist.x for h in recovered} == {LEFT: 256, RIGHT: 320}


def test_normal_nearby_two_hand_ema_unchanged(config):
    s = LandmarkStabilizer(config(smoothing_alpha=.7))
    s.update(0, 0., DIAG, None, [hand(LEFT, 256), hand(RIGHT, 320)])
    _, _, hands = s.update(1, .03, DIAG, None, [hand(LEFT, 266), hand(RIGHT, 330)])
    positions = {h.handedness: h.wrist.x for h in hands}
    assert positions[LEFT] == pytest.approx(263)
    assert positions[RIGHT] == pytest.approx(327)
    assert all(h.consecutive_frames == 2 for h in hands)


def test_expired_opposite_hand_cannot_reset_live_hand_ema(config):
    s = LandmarkStabilizer(config(smoothing_alpha=.7, max_hold_frames=1))
    s.update(0, 0., DIAG, None, [hand(LEFT, 256), hand(RIGHT, 320)])
    s.update(1, .03, DIAG, None, [hand(LEFT, 256)])
    _, _, hands = s.update(3, .09, DIAG, None, [hand(LEFT, 300)])
    assert len(hands) == 1 and hands[0].wrist.x == pytest.approx(286.8)
