"""Optional: real local MediaPipe models (skipped when the .task files are absent).

Uses synthetic frames only, so it verifies loading, VIDEO-mode timestamps,
empty-scene behaviour and partial-model degradation, NOT landmark accuracy.
"""

from dataclasses import replace
from pathlib import Path

import pytest
from pose_tracking.config import load_config
from pose_tracking.tracker import PoseHandTracker

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
