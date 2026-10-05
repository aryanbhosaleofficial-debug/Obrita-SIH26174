"""Real inference gates: missing production assets are explicit skips, not fakes."""
from pathlib import Path
from importlib.util import find_spec
import pytest
import numpy as np
from shared.config import PipelineConfig
from shared.schemas.frame_packet import FramePacket
from perception.core import FrameProcessor

ROOT = Path(__file__).resolve().parents[1]
pytestmark = pytest.mark.inference


def required(path, what):
    if path is None or not path.is_file():
        pytest.skip(f"REAL {what} INFERENCE NOT VERIFIED: missing local model {path}")


def test_real_yolo_inference():
    from yolo.pipeline import YoloPipeline
    config = PipelineConfig.from_yaml(ROOT / "configs/pipeline.yaml")
    required(config.detector.model_path, "YOLO")
    if find_spec("ultralytics") is None:
        pytest.skip("real YOLO inference requires local ultralytics installation")
    image = np.zeros((240, 320, 3), np.uint8)
    prepared = FrameProcessor().process(FramePacket(0, 0.0, image, 320, 240))
    stage = YoloPipeline(config.detector)
    try:
        stage.initialize()
        result = stage.process(prepared)
        assert result.frame_id == 0 and result.image_width == 320
        assert result.status.value in ("ok", "no_detection")
    finally:
        stage.close()


def test_real_pose_inference():
    from pose_tracking.config import load_config
    from optimization.pose.pose_tracker import MediaPipePoseTracker
    config = load_config()
    required(config.pose_model_path, "POSE")
    pytest.importorskip("mediapipe", reason="real pose inference requires local mediapipe installation")
    helper = MediaPipePoseTracker(config)
    try:
        helper.initialize()
        assert isinstance(helper.track_at(np.zeros((240, 320, 3), np.uint8), 0.0), list)
    finally:
        helper.close()


def test_real_hand_inference():
    from optimization.hands.hand_tracker import MediaPipeHandTracker
    config = PipelineConfig.from_yaml(ROOT / "configs/pipeline.yaml").hand_tracker
    required(config.model_path, "HAND")
    pytest.importorskip("mediapipe", reason="real hand inference requires local mediapipe installation")
    helper = MediaPipeHandTracker(config)
    try:
        helper.initialize()
        assert isinstance(helper.track(np.zeros((240, 320, 3), np.uint8), timestamp_s=0.0), list)
    finally:
        helper.close()
