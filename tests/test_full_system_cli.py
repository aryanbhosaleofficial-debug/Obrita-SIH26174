"""Portable authoritative launchers, offline mode and Qt worker shutdown."""
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest
import cv2
import numpy as np

from integration.full_cli import ROOT, main


def test_full_runner_from_external_directory_with_spaces(tmp_path):
    directory = tmp_path / "working directory with spaces"
    directory.mkdir()
    output = directory / "session events.jsonl"
    result = subprocess.run([sys.executable, str(ROOT / "scripts/run_full_pipeline.py"),
        "--synthetic", "--scenario", "recovery", "--no-gui", "--log", str(output)],
        cwd=directory, capture_output=True, text=True, timeout=30)
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout)["procedure_state"] == "completed"
    assert json.loads(output.read_text().splitlines()[-1])["event"] == "system_stopped"


def test_main_is_alias_of_authoritative_full_runner(tmp_path):
    result = subprocess.run([sys.executable, str(ROOT / "main.py"), "--synthetic",
        "--log", str(tmp_path / "events.jsonl")], cwd=tmp_path,
        capture_output=True, text=True, timeout=30)
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout)["completed_steps"] == ["step_1", "step_2", "step_3", "step_4"]


def test_full_gui_offscreen_updates_and_worker_exits(tmp_path):
    pytest.importorskip("PySide6")
    shot = tmp_path / "new folder" / "GUI result.png"
    result = subprocess.run([sys.executable, str(ROOT / "scripts/run_full_pipeline.py"),
        "--synthetic", "--gui", "--gui-shot", str(shot), "--log", str(tmp_path / "events.jsonl")],
        cwd=tmp_path, env={**os.environ, "QT_QPA_PLATFORM": "offscreen"},
        capture_output=True, text=True, timeout=30)
    assert result.returncode == 0, result.stderr
    assert shot.is_file() and shot.stat().st_size > 10000
    assert json.loads(result.stdout)["procedure_state"] == "completed"


def test_offline_verifier_runs_complete_logic_and_recording(tmp_path):
    result = subprocess.run([sys.executable, str(ROOT / "scripts/verify_full_system_offline.py"),
        "--synthetic", "--scenario", "recovery", "--no-gui", "--record", str(tmp_path / "offline.avi"),
        "--log", str(tmp_path / "events.jsonl")], cwd=tmp_path, capture_output=True, text=True, timeout=30)
    assert result.returncode == 0, result.stderr
    summary = json.loads(result.stdout)
    assert summary["procedure_state"] == "completed" and summary["recorded_frames"] > 0


def test_empty_camera_source_is_a_clean_failure(monkeypatch, tmp_path):
    from dataclasses import replace
    from shared.config import PipelineConfig
    from pose_tracking.config import load_config
    import pose_tracking.config as tracking
    import pose_tracking.tracker as trackers
    from pose_tracking.backends import NullLandmarkBackend
    import integration.sources as sources
    import integration.chain as chains
    from integration.mocks import MockDetector
    config = PipelineConfig.from_yaml(ROOT / "configs/pipeline.yaml")
    config.detector = replace(config.detector, backend="mock", tracking=False, model_path=None)
    config.hand_tracker = replace(config.hand_tracker, enabled=False)
    model = tmp_path / "inference-fake.task"
    model.write_bytes(b"placeholder; injected backend does not read this file")
    track = replace(load_config(), pose_model_path=model, hands_enabled=False)
    original_tracker = trackers.PoseHandTracker
    original_chain = chains.PerceptionChain
    monkeypatch.setattr(chains, "PerceptionChain", lambda cfg, **kw: original_chain(cfg, detector=MockDetector()))
    monkeypatch.setattr(trackers, "PoseHandTracker", lambda cfg, backend=None: original_tracker(cfg, NullLandmarkBackend()))
    monkeypatch.setattr(PipelineConfig, "from_yaml", classmethod(lambda cls, path: config))
    monkeypatch.setattr(tracking, "load_config", lambda path: track)
    monkeypatch.setattr(sources, "packets", lambda *args, **kwargs: iter(()))
    assert main(["--source", "0", "--procedure", str(ROOT / "procedures/fusion_touch_move.yaml"),
                 "--log", str(tmp_path / "events.jsonl")]) == 2
    assert "source produced no frames" in json.loads((tmp_path / "events.jsonl").read_text().splitlines()[-1])["error"]


def test_real_video_source_eof_preserves_identity_with_inference_fakes(monkeypatch, tmp_path):
    from dataclasses import replace
    from shared.config import PipelineConfig
    import pose_tracking.config as tracking
    import pose_tracking.tracker as trackers
    import integration.chain as chains
    from pose_tracking.backends import NullLandmarkBackend
    from integration.mocks import MockDetector
    config = PipelineConfig.from_yaml(ROOT / "configs/pipeline.yaml")
    config.detector = replace(config.detector, backend="mock", tracking=False, model_path=None)
    config.hand_tracker = replace(config.hand_tracker, enabled=False)
    model = tmp_path / "fake.task"
    model.write_bytes(b"unused by injected backend")
    track = replace(tracking.load_config(), pose_model_path=model, hands_enabled=False)
    original_chain, original_tracker = chains.PerceptionChain, trackers.PoseHandTracker
    monkeypatch.setattr(chains, "PerceptionChain", lambda cfg, **kw: original_chain(cfg, detector=MockDetector()))
    monkeypatch.setattr(trackers, "PoseHandTracker", lambda cfg, backend=None: original_tracker(cfg, NullLandmarkBackend()))
    monkeypatch.setattr(PipelineConfig, "from_yaml", classmethod(lambda cls, path: config))
    monkeypatch.setattr(tracking, "load_config", lambda path: track)
    source = tmp_path / "video input with spaces.avi"
    writer = cv2.VideoWriter(str(source), cv2.VideoWriter.fourcc(*"MJPG"), 10., (80, 64))
    assert writer.isOpened()
    for _ in range(8):
        writer.write(np.zeros((64, 80, 3), np.uint8))
    writer.release()
    log, diagnostics = tmp_path / "events.jsonl", tmp_path / "frames.jsonl"
    assert main(["--source", str(source), "--no-gui", "--procedure", str(ROOT / "procedures/fusion_touch_move.yaml"),
                 "--log", str(log), "--diagnostics", str(diagnostics)]) == 0
    summary = json.loads(log.read_text().splitlines()[-1])
    assert summary["frames"] == 8 and summary["exit_reason"] == "eof"
    assert summary["procedure_state"] == "ready"  # no fabricated activities
    frames = [json.loads(line) for line in diagnostics.read_text().splitlines()]
    assert [r["frame_id"] for r in frames] == list(range(8))
    assert all(r["source_id"] == str(source) == r["tracking"]["source_id"] for r in frames)
