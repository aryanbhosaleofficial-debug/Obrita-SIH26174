"""Optional: real local MediaPipe models (skipped when the .task files are absent).

Uses synthetic frames only, so it verifies loading, VIDEO-mode timestamps,
empty-scene behaviour and partial-model degradation, NOT landmark accuracy.
"""

from dataclasses import replace
from pathlib import Path
import os

import cv2
import pytest
from pose_tracking.config import load_config
from pose_tracking.tracker import PoseHandTracker
from perception.core import FrameProcessor
from shared.schemas.frame_packet import FramePacket

from shared.diagnostics import WarningCode
from shared.enums.module_status import ModuleStatus

pytest.importorskip("mediapipe")
CONFIG = load_config()
if not (CONFIG.pose_model_path.is_file() and CONFIG.hand_model_path.is_file()):
    pytest.skip("local MediaPipe .task models not installed", allow_module_level=True)


def test_real_models_empty_scene(frames):
    make = frames(320, 240)
    with PoseHandTracker(CONFIG) as tracker:
        results = [tracker.process(make()) for _ in range(5)]
        tracker.reset()  # recreates landmarkers; later timestamps still accepted
        results.append(tracker.process(make()))
    assert all(r.status == ModuleStatus.NO_DETECTION for r in results)
    assert all(r.body_landmarks == () and r.hands == () for r in results)


def test_real_hand_model_alone_when_pose_model_missing(frames):
    config = replace(CONFIG, pose_model_path=Path("missing/pose.task")).validate()
    with PoseHandTracker(config) as tracker:
        pose = tracker.process(frames(320, 240)())
    assert pose.status == ModuleStatus.DEGRADED
    assert WarningCode.POSE_TRACKER_FAILURE in {w.code for w in pose.warnings}


def sample(name):
    directory = Path(os.environ.get("SIH_MODULE06_SAMPLE_DIR", "tests_tmp/module06"))
    path = directory / name
    if not path.is_file():
        pytest.skip(f"optional local Google sample missing: {path}; see Module 06 models README")
    image = cv2.imread(str(path))
    assert image is not None, f"cannot decode supplied sample {path}"
    return image


def prepared(image):
    h, w = image.shape[:2]
    return FrameProcessor().process(FramePacket(0, 0.0, image, w, h))


def test_real_pose_positive_sample():
    with PoseHandTracker(CONFIG) as tracker:
        output = tracker.process(prepared(sample("pose.jpg")))
    assert output.body_detected and len(output.body_landmarks) == 33
    assert any(p.is_valid for p in output.body_landmarks)
    assert output.inference_ms > 0


@pytest.mark.parametrize("mirrored", [False, True])
def test_real_two_hands_and_tasks_mirror_convention(mirrored):
    image = sample("right_hands.jpg")  # Google's two-right-hands fixture, NOT one person
    if mirrored:
        image = cv2.flip(image, 1)
    with PoseHandTracker(replace(CONFIG, input_mirrored=mirrored)) as tracker:
        output = tracker.process(prepared(image))
    assert len(output.hands) == 2 and output.right_hand_detected
    assert not output.left_hand_detected  # duplicate side is explicitly UNKNOWN
    assert all(h.model_handedness == ("Left" if mirrored else "Right") for h in output.hands)
    assert all(len(h.landmarks) == 21 and h.observed for h in output.hands)
