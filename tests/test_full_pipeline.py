"""Headless milestone CLI integration; all inference is explicitly faked."""
import json
from pathlib import Path
import subprocess
import sys
import pytest
from integration.cli import main, camera_main

ROOT = Path(__file__).resolve().parents[1]


def test_events_written(tmp_path):
    output = tmp_path / "frames.jsonl"
    events = tmp_path / "events.jsonl"
    assert main(["--synthetic", "--output", str(output), "--events", str(events)]) == 0
    rows = [json.loads(line) for line in output.read_text().splitlines()]
    emitted = [json.loads(line) for line in events.read_text().splitlines()]
    assert len(rows) == 36
    assert [r["activity_label"] for r in emitted] == ["touch_object", "move_object"]
    assert rows[-1]["activity"]["activity_label"] == "unknown"
    assert all(row["mode"] == "synthetic" for row in rows)
    assert all(set(row["statuses"]) == {"01", "02", "03", "04", "05"} for row in rows)


def test_timing_measured(tmp_path):
    output = tmp_path / "frames.jsonl"
    assert main(["--synthetic", "--max-frames", "8", "--output", str(output),
                 "--events", str(tmp_path / "events.jsonl")]) == 0
    for row in map(json.loads, output.read_text().splitlines()):
        for name in ("preprocessing_ms", "object_detection_ms", "hand_tracking_ms",
                     "coordinate_transform_ms", "boundary_ms", "fusion_ms", "pipeline_ms"):
            assert row["timings_ms"][name] >= 0


@pytest.mark.parametrize("script", ["run_fusion.py", "run_camera.py"])
def test_direct_script_from_other_directory(tmp_path, script):
    args = [sys.executable, str(ROOT / "scripts" / script), "--synthetic", "--max-frames", "6"]
    if script == "run_fusion.py":
        args += ["--events", str(tmp_path / "events.jsonl")]
    result = subprocess.run(args, cwd=tmp_path, capture_output=True, text=True, timeout=30)
    assert result.returncode == 0, result.stderr
    rows = [json.loads(line) for line in result.stdout.splitlines()]
    assert len(rows) == 6
    assert rows[0]["frame_id"] == 0


def test_missing_real_assets_fail_before_camera(monkeypatch, capsys, tmp_path):
    def forbidden(*args, **kwargs):
        raise AssertionError("camera must not open before missing asset validation")
    import integration.sources as sources
    monkeypatch.setattr(sources, "OpenCVSource", forbidden)
    absent = tmp_path / "absent.pt"
    assert main(["--camera", "0", "--model", str(absent), "--hand-model", str(tmp_path / "hand.task"),
                 "--pose-model", str(tmp_path / "pose.task")]) == 2
    message = capsys.readouterr().err
    assert "YOLO model not found" in message and "--model" in message
    assert "hand model not found" in message and "--hand-model" in message
    assert "pose model not found" in message and "--pose-model" in message
    assert "Traceback" not in message


def test_output_cannot_overwrite_config_or_input(tmp_path):
    assert main(["--synthetic", "--output", str(ROOT / "configs/fusion.yaml")]) == 2
    assert camera_main(["--synthetic", "--max-frames", "0"]) == 2
    same = tmp_path / "same.jsonl"
    assert main(["--synthetic", "--output", str(same), "--events", str(same)]) == 2


def test_ctrl_c_releases_sources_and_models(monkeypatch, tmp_path):
    import integration.cli as cli
    import integration.chain as chain
    from integration.synthetic import scene, configure
    from shared.config import PipelineConfig
    frames, detector, hands = scene()
    closed = []
    def interrupted():
        try:
            yield frames[0]
            raise KeyboardInterrupt
        finally:
            closed.append(True)
    monkeypatch.setattr(cli, "source_frames", lambda *args: (interrupted(), detector, hands, "unit"))
    assert main(["--synthetic", "--output", str(tmp_path / "frames.jsonl"),
                 "--events", str(tmp_path / "events.jsonl")]) == 130
    assert closed and detector.closed and hands.closed
