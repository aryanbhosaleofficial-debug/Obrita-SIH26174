"""Integration of historical main entry points with the rebased canonical API."""

import ast
import importlib
import json
from pathlib import Path
import subprocess
import sys

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[1]


def test_numbered_optimization_exports_are_canonical():
    owner = importlib.import_module("03_optimization")
    canonical = importlib.import_module("optimization.pipeline")
    assert owner.OptimizationPipeline is canonical.OptimizationPipeline
    assert owner.OptimizationSequencePipeline is canonical.OptimizationPipeline
    assert owner.OptimizationSequence is importlib.import_module("optimization").OptimizationSequence


@pytest.mark.parametrize("direct", [False, True])
def test_procedure_runner_preserves_configured_step_ids(tmp_path, direct):
    command = [sys.executable, str(ROOT / "main.py")]
    cwd = ROOT
    if direct:
        command = [sys.executable, str(ROOT / "scripts/run_full_pipeline.py"),
                   str(ROOT / "procedures/demo_experiment.yaml"), str(ROOT / "configs")]
        cwd = tmp_path
    result = subprocess.run(command, cwd=cwd, capture_output=True, text=True, timeout=30)
    assert result.returncode == 0, result.stderr
    assert "step_01 -> correct" in result.stdout and "step_02 -> correct" in result.stdout
    assert "Completed steps: ['step_01', 'step_02']" in result.stdout


def test_numbered_optimization_replay_confirms_then_expires():
    result = subprocess.run([sys.executable, "-m", "03_optimization"], cwd=ROOT,
                            capture_output=True, text=True, timeout=30)
    assert result.returncode == 0, result.stderr
    packets = [json.loads(line) for line in result.stdout.splitlines()]
    assert any(packet["quality_ok"] for packet in packets)
    assert packets[-1]["object_frame"]["detections"] == []


def test_historical_contour_and_contact_utilities_remain_available():
    associate = importlib.import_module("boundary.contour.contour_association").associate_contour
    resample = importlib.import_module("boundary.contour.contour_resampler").resample_contour
    contact = importlib.import_module("boundary.features.contact_detector").detect_contact
    contour = np.array([[10, 10], [30, 10], [30, 30], [10, 30]], np.int32).reshape(-1, 1, 2)
    assert associate([contour + 60, contour], target_bbox=(10, 10, 20, 20)) is contour
    assert resample(contour, count=16).shape == (16, 2)
    assert not contact({"available": False})["contact"]


def test_historical_motion_and_gesture_utilities_remain_available():
    displacement = importlib.import_module("optimization.motion.displacement").displacement
    velocity = importlib.import_module("optimization.motion.velocity").velocity
    angle = importlib.import_module("optimization.motion.joint_angles").joint_angle
    recognize = importlib.import_module("optimization.gesture.gesture_recognizer").recognize
    assert displacement((1, 2), (4, 6)) == (3, 4)
    assert velocity((1, 2), (4, 6), 10, 12) == (1.5, 2)
    assert angle((1, 0), (0, 0), (0, 1)) == pytest.approx(90)
    assert recognize([]).label == "unknown"


def test_optional_yolo_demo_does_not_download_missing_weights(tmp_path):
    tree = ast.parse((ROOT / "04_boundary/streamlit_app.py").read_text(encoding="utf-8"))
    loader = next(node for node in tree.body if isinstance(node, ast.FunctionDef)
                  and node.name == "object_detector")
    loader.decorator_list = []
    calls = []
    namespace = {"Path": Path, "YOLO": lambda path: calls.append(path)}
    exec(compile(ast.Module(body=[loader], type_ignores=[]), "loader", "exec"), namespace)
    assert namespace["object_detector"]("") is None
    assert namespace["object_detector"](str(tmp_path / "missing.pt")) is None
    assert not calls


def test_optional_streamlit_synthetic_demo(monkeypatch):
    pytest.importorskip("streamlit.testing.v1")
    from streamlit.testing.v1 import AppTest

    monkeypatch.setitem(sys.modules, "mediapipe", None)
    monkeypatch.setitem(sys.modules, "ultralytics", None)
    app = AppTest.from_file(str(ROOT / "04_boundary/streamlit_app.py"), default_timeout=15).run()
    assert not app.exception
    assert app.metric[0].value == "ModuleStatus.OK"
    app.checkbox[1].check().run()
    assert not app.exception
    assert app.text_input[0].value == ""
