"""Exercise actual standalone entry points without GUI, inference, or internet."""

import json
import subprocess
import sys
from pathlib import Path

import cv2

ROOT = Path(__file__).resolve().parents[2]


def run_cli(*args, cwd=ROOT):
    return subprocess.run(
        [sys.executable, "-m", "boundary.standalone_cli", *map(str, args)],
        cwd=cwd,
        capture_output=True,
        text=True,
        check=False,
    )


def test_synthetic_cli():
    result = run_cli("--synthetic", "--frames", 3)
    assert result.returncode == 0, result.stderr
    packets = [json.loads(row) for row in result.stdout.splitlines()]
    assert len(packets) == 3 and all(
        p["contour_px"] and p["quality_ok"] for p in packets
    )


def test_local_image_and_script_launcher(image, tmp_path):
    path, output = tmp_path / "scene.png", tmp_path / "output.jsonl"
    assert cv2.imwrite(str(path), image)
    result = run_cli("--image", path, "--output", output)
    assert result.returncode == 0, result.stderr
    assert json.loads(output.read_text())["chain_code"]
    result = subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts/run_boundary.py"),
            "--synthetic",
            "--frames",
            "1",
        ],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr


def test_cli_rejects_invalid_input_and_path_collision(tmp_path):
    path = tmp_path / "missing.png"
    assert run_cli("--image", path).returncode == 2
    assert run_cli("--image", path, "--output", path).returncode == 2
    assert run_cli("--synthetic", "--frames", 0).returncode == 2


def test_cli_rack_valid_is_an_explicit_caller_assertion():
    args = ("--synthetic", "--frames", 1, "--config", ROOT / "configs/boundary.yaml")
    rejected = run_cli(*args)
    accepted = run_cli(*args, "--rack-valid")
    assert rejected.returncode == accepted.returncode == 0
    assert not json.loads(rejected.stdout)["quality_ok"]
    assert json.loads(accepted.stdout)["quality_ok"]
    assert json.loads(accepted.stdout)["orientation_deg_rack"] is None
