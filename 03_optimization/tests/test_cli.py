"""Real subprocess CLI checks, using only synthetic/shared packets."""

import json
import subprocess
import sys
from dataclasses import asdict
from pathlib import Path

import pytest
from optimization.standalone_cli import decode_object_frame

ROOT = Path(__file__).resolve().parents[2]


def run_cli(*args):
    return subprocess.run(
        [sys.executable, "-m", "optimization.standalone_cli", *map(str, args)],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )


def test_synthetic_cli_runs_without_models():
    result = run_cli("--synthetic")
    assert result.returncode == 0, result.stderr
    packets = [json.loads(line) for line in result.stdout.splitlines()]
    assert len(packets) == 9
    assert not packets[0]["stable_detections"]
    assert packets[2]["stable_detections"][0]["observed"]
    assert not packets[3]["stable_detections"][0]["observed"]
    assert not packets[-1]["stable_detections"]


@pytest.mark.parametrize(
    "envelope,suffix", [(False, ".json"), (False, ".jsonl"), (True, ".jsonl")]
)
def test_replays_shared_or_module02_json(
    tmp_path, object_frame, detection, envelope, suffix
):
    frames = [asdict(object_frame(i, [detection()])) for i in range(3)]
    values = [{"objects": f, "semantic": None} for f in frames] if envelope else frames
    path, output = tmp_path / ("input" + suffix), tmp_path / "output.jsonl"
    path.write_text(
        json.dumps(values)
        if suffix == ".json"
        else "\n".join(json.dumps(v) for v in values),
        encoding="utf-8",
    )
    result = run_cli("--input", path, "--output", output)
    assert result.returncode == 0, result.stderr
    packets = [json.loads(line) for line in output.read_text().splitlines()]
    assert packets[-1]["stable_detections"][0]["track_id"] == 7
    assert decode_object_frame(values[0]).detections[0].bbox == detection().bbox


def test_cli_error_and_script_entrypoint(tmp_path):
    path = tmp_path / "bad.jsonl"
    path.write_text('{"frame_id":', encoding="utf-8")
    result = run_cli("--input", path)
    assert result.returncode == 2 and "line 1" in result.stderr
    assert run_cli("--input", path, "--output", path).returncode == 2
    result = subprocess.run(
        [sys.executable, str(ROOT / "scripts/run_optimization.py"), "--synthetic"],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
