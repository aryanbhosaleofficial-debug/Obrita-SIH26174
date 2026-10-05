"""Optional body helper adapter tests inject inference, never production weights."""
from pathlib import Path
from types import SimpleNamespace
import sys
import numpy as np
import pytest

from optimization.pose.pose_tracker import MediaPipePoseTracker
from pose_tracking.config import PoseTrackingConfig, load_config
from shared.errors import InitializationError


class Backend:
    def __init__(self):
        self.initializations = 0
        self.closed = False
        self.timestamps = []
    def initialize(self):
        self.initializations += 1
    def detect(self, image, timestamp):
        self.timestamps.append(timestamp)
        return SimpleNamespace(body=[
            SimpleNamespace(x=0.25, y=0.5, visibility=0.9, presence=0.8)
            for _ in range(33)])
    def close(self):
        self.closed = True


def test_pose_inference_adapter_initializes_once_and_preserves_source_time():
    fake = Backend()
    config = PoseTrackingConfig(pose_model_path=Path("not-used-with-injected-backend.task"),
                                hands_enabled=False)
    helper = MediaPipePoseTracker(config, backend=fake)
    for ts in (1.0, 1.1, 1.2):
        poses = helper.track_at(np.zeros((60, 80, 3), np.uint8), ts)
        assert len(poses[0].landmarks) == 33
        assert poses[0].landmarks[0].x == 20
        assert poses[0].landmarks[0].y == 30
        assert poses[0].confidence == 0.8
    assert fake.initializations == 1
    assert fake.timestamps == [1.0, 1.1, 1.2]
    helper.close()
    assert fake.closed


def test_missing_pose_asset_is_clear_before_mediapipe_import(monkeypatch, tmp_path):
    monkeypatch.setitem(sys.modules, "mediapipe", None)
    helper = MediaPipePoseTracker(PoseTrackingConfig(
        pose_model_path=tmp_path / "absent.task", hands_enabled=False))
    with pytest.raises(InitializationError, match="provide --pose-model"):
        helper.initialize()


def test_helper_config_resolves_real_default_asset():
    config = load_config()
    assert config.pose_model_path.name == "pose_landmarker_lite.task"
    assert config.pose_model_path.parent.name == "models"
    assert config.hand_model_path.name == "hand_landmarker.task"
