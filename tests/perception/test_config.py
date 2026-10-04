from pathlib import Path

import pytest

from perception.config import ConfigurationError, PerceptionConfig

ROOT = Path(__file__).resolve().parents[2]


def test_shipped_configs_and_relative_model_paths():
    real = PerceptionConfig.from_yaml(ROOT / "configs/perception_demo.yaml")
    mock = PerceptionConfig.from_yaml(ROOT / "configs/perception_mock.yaml")
    assert real.detector.model_path == ROOT / "02_yolo/models/experiment_objects.pt"
    assert real.hand_tracker.model_path == ROOT / "models/hand_landmarker.task"
    assert mock.detector.backend == "mock" and mock.reference_frame.enabled


@pytest.mark.parametrize(
    "content",
    [
        "",
        "[]",
        "perception: []",
        "perception: {}\nextra: {}",
        "perception: [broken",
        "perception:\n  detector:\n    typo: 1",
        "perception:\n  typo: {}",
        "perception:\n  detector:\n    confidence_threshold: 1.1",
        "perception:\n  hand_tracker:\n    max_hands: 0",
        "perception:\n  reference_frame:\n    enabled: true",
        "perception:\n  reference_frame:\n    type: unknown",
        "perception:\n  stabilization:\n    ema_alpha: 0",
        "perception:\n  interaction:\n    contact_threshold: .5",
        "perception:\n  detector:\n    cpu_fallback: 'false'",
        "perception:\n  detector:\n    class_whitelist: [true]",
        "perception:\n  preprocessing:\n    max_width: 1.5",
        "perception:\n  interaction:\n    proximity_threshold: .nan",
    ],
)
def test_invalid_yaml_settings_fail_clearly(tmp_path, content):
    path = tmp_path / "config.yaml"
    path.write_text(content)
    with pytest.raises((ConfigurationError, ValueError)):
        PerceptionConfig.from_yaml(path)


def test_direct_config_validation(config):
    config.stabilization.detection_min_frames = True
    with pytest.raises(ConfigurationError):
        config.validate()
