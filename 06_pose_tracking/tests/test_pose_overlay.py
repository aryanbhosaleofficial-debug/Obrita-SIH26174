"""Overlay renderer: detached output, frame-sync guard, robustness. No GUI window."""

import numpy as np
import pytest
from pose_tracking.contracts import LEFT, HandPose, Landmark, PoseFrame
from pose_tracking.landmarks import BODY_LANDMARK_NAMES, HAND_LANDMARK_NAMES
from pose_tracking.sync import FrameSyncError
from pose_tracking.visualization import (
    draw_hands,
    draw_objects,
    draw_pose,
    render_overlay,
    status_lines,
)

from shared.schemas.object_frame import ObjectFrame
from shared.schemas.observations import BoundingBox, Detection


def source():
    return np.zeros((240, 320, 3), np.uint8)


def pose_frame(**kwargs):
    body = tuple(
        Landmark(i, n, 100 + (i % 5) * 10, 40 + i * 5, 0.0, 0.95)
        for i, n in enumerate(BODY_LANDMARK_NAMES)
    )
    hand = HandPose(
        LEFT,
        tuple(
            Landmark(i, n, 200 + i * 3, 150 + i * 2, 0.0)
            for i, n in enumerate(HAND_LANDMARK_NAMES)
        ),
    )
    values = {
        "frame_id": 3,
        "timestamp_s": 0.1,
        "body_landmarks": body,
        "body_detected": True,
        "hands": (hand,),
        "image_width": 320,
        "image_height": 240,
    }
    values.update(kwargs)
    return PoseFrame(**values)


def objects(frame_id=3):
    return ObjectFrame(
        frame_id,
        0.1,
        320,
        240,
        detections=[Detection(0, "blue_tube", 0.9, BoundingBox(10, 10, 60, 90), 4)],
    )


def test_render_is_detached_and_draws_everything():
    image = source()
    display = render_overlay(image, pose_frame(), objects(), fps=12.3)
    assert display is not image and not image.any()  # source untouched
    assert display[40:200, 90:150].any()  # body skeleton
    assert display[150:200, 195:265].any()  # hand skeleton
    assert display[10, 10:60].any()  # object box edge


def test_held_and_empty_frames_render():
    held = pose_frame(
        body_detected=False,
        body_frames_since_seen=1,
        hands=(
            HandPose(
                LEFT,
                pose_frame().hands[0].landmarks,
                observed=False,
                frames_since_seen=1,
            ),
        ),
    )
    assert render_overlay(source(), held).any()
    empty = PoseFrame(1, 0.0, image_width=320, image_height=240)
    out = render_overlay(source(), empty)
    assert out[30:, :].sum() == 0  # only the status text area is drawn


def test_low_visibility_and_far_off_image_points_are_skipped():
    body = tuple(
        Landmark(i, n, 1e6, -1e6, 0.0, 0.1) for i, n in enumerate(BODY_LANDMARK_NAMES)
    )
    image = source()
    draw_pose(image, PoseFrame(0, 0.0, body_landmarks=body, body_detected=True))
    assert not image.any()


def test_draw_functions_tolerate_empty_inputs():
    image = source()
    draw_pose(image, PoseFrame(0, 0.0))
    draw_hands(image, PoseFrame(0, 0.0))
    draw_objects(image, ObjectFrame(0, 0.0, 320, 240))
    assert not image.any()


def test_overlay_refuses_mixed_frames():
    with pytest.raises(FrameSyncError):
        render_overlay(source(), pose_frame(), objects(frame_id=4))
    with pytest.raises(FrameSyncError):
        render_overlay(np.zeros((100, 100, 3), np.uint8), pose_frame())
    with pytest.raises(ValueError):
        render_overlay(np.zeros((240, 320), np.uint8), pose_frame())


def test_status_lines_report_held_state():
    lines = status_lines(
        pose_frame(body_detected=False, body_frames_since_seen=2), objects(), fps=9.0
    )
    assert (
        "Body:held" in lines[0]
        and "YOLO:ok objects:1" in lines[1]
        and "measured" in lines[2]
    )
