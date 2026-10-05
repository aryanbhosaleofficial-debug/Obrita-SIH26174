"""Standalone CLI and live sources without camera hardware or a display."""

import json
import subprocess
import sys
import time
from itertools import pairwise
from pathlib import Path

import cv2
import numpy as np
import pytest
from pose_tracking import cli
from pose_tracking.sources import LatestFrameCamera, SourceError, file_frames
from pose_tracking.tracker import PoseHandTracker

MODULE_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = MODULE_ROOT.parent


class FakeCapture:
    def __init__(self, *, fail=False, opened=True, delay_s=0.001):
        self.fail, self.opened, self.delay_s = fail, opened, delay_s
        self.count = 0
        self.released = False

    def isOpened(self):
        return self.opened

    def set(self, *args):
        return True

    def read(self):
        time.sleep(self.delay_s)
        if self.fail:
            return False, None
        self.count += 1
        return True, np.full((4, 4, 3), self.count % 256, np.uint8)

    def release(self):
        self.released = True


def test_latest_frame_camera_drops_stale_frames_instead_of_queueing():
    capture = FakeCapture()
    camera = LatestFrameCamera(0, capture_factory=lambda _: capture)
    try:
        time.sleep(0.1)  # consumer is "slow": many frames captured meanwhile
        first = camera.read(1.0)
        assert first is not None and first.frame_id > 1
        assert first.dropped_frames_before == first.frame_id  # all older frames skipped
        time.sleep(0.05)
        second = camera.read(1.0)
        assert second.frame_id > first.frame_id
        assert second.dropped_frames_before == second.frame_id - first.frame_id - 1
        assert second.timestamp_s > first.timestamp_s
        assert set(vars(camera)) >= {"_slot"} and isinstance(
            camera._slot, tuple
        )  # one slot
    finally:
        camera.close()
    assert capture.released


def test_camera_read_failure_raises_after_limit():
    camera = LatestFrameCamera(
        0, read_failure_limit=5, capture_factory=lambda _: FakeCapture(fail=True)
    )
    try:
        with pytest.raises(SourceError, match="failed"):
            camera.read(2.0)
    finally:
        camera.close()


def test_camera_open_failure():
    with pytest.raises(SourceError, match="cannot open"):
        LatestFrameCamera(3, capture_factory=lambda _: FakeCapture(opened=False))


def write_video(path: Path, count=6):
    writer = cv2.VideoWriter(str(path), cv2.VideoWriter.fourcc(*"mp4v"), 10.0, (64, 48))
    assert writer.isOpened()
    for i in range(count):
        writer.write(np.full((48, 64, 3), 20 * i, np.uint8))
    writer.release()


def test_file_frames_reads_sequential_video(tmp_path):
    video = tmp_path / "clip.mp4"
    write_video(video)
    frames = list(file_frames(video))
    assert [f.frame_id for f in frames] == list(range(6))
    assert frames[1].timestamp_s == pytest.approx(0.1)
    with pytest.raises(SourceError):
        list(file_frames(tmp_path / "missing.mp4"))


@pytest.fixture
def scripted_cli(monkeypatch, raw):
    backend = raw.Backend([raw.result(raw.body(), (raw.hand("Left"),))])
    monkeypatch.setattr(
        cli, "PoseHandTracker", lambda config: PoseHandTracker(config, backend)
    )
    return backend


def test_cli_video_headless_writes_synchronized_jsonl(tmp_path, scripted_cli):
    video, out = tmp_path / "clip.mp4", tmp_path / "pose.jsonl"
    write_video(video)
    annotated = tmp_path / "annotated.mp4"
    code = cli.main(
        [
            "--source",
            str(video),
            "--no-display",
            "--jsonl",
            str(out),
            "--output",
            str(annotated),
        ]
    )
    assert code == 0
    rows = [json.loads(line) for line in out.read_text(encoding="utf-8").splitlines()]
    assert [r["frame_id"] for r in rows] == list(range(6))
    assert [r["timestamp_s"] for r in rows] == pytest.approx([i / 10 for i in range(6)])
    assert all(r["source_id"] == "clip.mp4" and r["body_detected"] for r in rows)
    assert rows[0]["hands"][0]["handedness"] == "RIGHT"
    assert annotated.stat().st_size > 0 and scripted_cli.initializations == 1


def test_cli_max_frames_and_image_output(tmp_path, scripted_cli):
    image = tmp_path / "frame.png"
    cv2.imwrite(str(image), np.zeros((48, 64, 3), np.uint8))
    out = tmp_path / "out.png"
    assert cli.main(["--source", str(image), "--no-display", "--output", str(out)]) == 0
    assert cv2.imread(str(out)) is not None
    video = tmp_path / "clip.mp4"
    write_video(video)
    jsonl = tmp_path / "two.jsonl"
    assert (
        cli.main(
            [
                "--source",
                str(video),
                "--no-display",
                "--max-frames",
                "2",
                "--jsonl",
                str(jsonl),
            ]
        )
        == 0
    )
    assert len(jsonl.read_text(encoding="utf-8").splitlines()) == 2


def test_cli_yolo_initialization_failure_keeps_pose_running(tmp_path, scripted_cli):
    video = tmp_path / "clip.mp4"
    write_video(video, 2)
    code = cli.main(
        [
            "--source",
            str(video),
            "--no-display",
            "--yolo",
            "--yolo-config",
            str(tmp_path / "missing.yaml"),
        ]
    )
    assert code == 0 and scripted_cli.calls == 2


def test_cli_missing_models_exit_cleanly(tmp_path):
    config = tmp_path / "pose.yaml"
    config.write_text(
        "pose_tracking:\n  pose_model_path: nope/pose.task\n  hand_model_path: nope/hand.task\n",
        encoding="utf-8",
    )
    image = tmp_path / "frame.png"
    cv2.imwrite(str(image), np.zeros((8, 8, 3), np.uint8))
    assert (
        cli.main(["--source", str(image), "--no-display", "--config", str(config)]) == 2
    )


def test_cli_camera_failure_exits_cleanly(monkeypatch, scripted_cli):
    def broken(*args, **kwargs):
        raise SourceError("cannot open camera 0")

    monkeypatch.setattr(cli, "LatestFrameCamera", broken)
    assert cli.main(["--camera", "0", "--no-display"]) == 2


def test_cli_rejects_bad_arguments(tmp_path, scripted_cli):
    assert (
        cli.main(
            ["--source", str(tmp_path / "x.mp4"), "--no-display", "--max-frames", "0"]
        )
        == 2
    )
    with pytest.raises(SystemExit):
        cli.main(["--camera", "0", "--source", "x.mp4"])


@pytest.mark.parametrize(
    "command",
    [
        [sys.executable, str(MODULE_ROOT / "standalone.py"), "--help"],
        [sys.executable, "-m", "06_pose_tracking", "--help"],
    ],
)
def test_entry_points_start(command):
    result = subprocess.run(
        command, cwd=REPO_ROOT, capture_output=True, text=True, timeout=120, check=False
    )
    assert result.returncode == 0, result.stderr
    assert "--camera" in result.stdout and "--yolo" in result.stdout


def test_camera_timestamps_strictly_increase_even_with_a_coarse_clock(monkeypatch):
    # Regression: Windows time.monotonic() ticks every ~15.6 ms, which produced
    # duplicate timestamps at 30 FPS and Module 01 rejected every other frame.
    from pose_tracking import sources

    monkeypatch.setattr(sources, "perf_counter", lambda: 100.0)  # frozen clock
    camera = LatestFrameCamera(0, capture_factory=lambda _: FakeCapture(delay_s=0.005))
    try:
        stamps = []
        while len(stamps) < 5:
            frame = camera.read(1.0)
            assert frame is not None
            stamps.append(frame.timestamp_s)
    finally:
        camera.close()
    assert all(b > a for a, b in pairwise(stamps))
