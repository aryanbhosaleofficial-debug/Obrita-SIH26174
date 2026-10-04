"""Real local YOLO smoke, capture/output and copied-package offline verification.

Requires the explicitly supplied HAR best.pt and installed dependencies. Synthetic
inputs verify execution, not accuracy or physical interaction interpretation.
"""

import json
import os
import shutil
import socket
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OWNER = ROOT / "02_yolo"
OUTPUT = (
    Path(os.environ["ORBITA_VERIFY_DIR"])
    if "ORBITA_VERIFY_DIR" in os.environ
    else Path(tempfile.mkdtemp(prefix="orbita-module02-runtime-"))
)
OUTPUT.mkdir(parents=True, exist_ok=True)
os.environ["YOLO_CONFIG_DIR"] = str(OUTPUT / "ultralytics")
os.environ["MPLCONFIGDIR"] = str(OUTPUT / "matplotlib")
os.environ["YOLO_OFFLINE"] = "true"
os.environ["YOLO_AUTOINSTALL"] = "false"
sys.path.insert(0, str(ROOT))


def no_network(*args, **kwargs):
    raise AssertionError("runtime attempted network access")


socket.socket.connect = no_network
socket.socket.sendto = no_network
socket.getaddrinfo = no_network

import cv2
import numpy as np
from optimization.pipeline import OptimizationPipeline
from yolo.config import load_config
from yolo.pipeline import YoloPipeline
from yolo.standalone_cli import main

from perception.core import FrameProcessor
from shared.config import HandTrackerConfig, PipelineConfig, PreprocessingConfig
from shared.schemas.frame_packet import FramePacket


def verify():
    image = np.full((240, 320, 3), 180, np.uint8)
    cv2.rectangle(image, (40, 100), (110, 170), (0, 0, 255), -1)
    photo = OUTPUT / "input.png"
    assert cv2.imwrite(str(photo), image)
    video = OUTPUT / "input.mp4"
    writer = cv2.VideoWriter(
        str(video), cv2.VideoWriter_fourcc(*"mp4v"), 10, (320, 240)
    )
    assert writer.isOpened()
    for i in range(4):
        writer.write(np.roll(image, i * 10, axis=1))
    writer.release()
    assert (
        main(
            [
                "--source",
                str(photo),
                "--device",
                "cpu",
                "--no-display",
                "--output",
                str(OUTPUT / "annotated.png"),
                "--jsonl",
                str(OUTPUT / "image.jsonl"),
            ]
        )
        == 0
    )
    assert (
        main(
            [
                "--source",
                str(video),
                "--device",
                "cpu",
                "--no-display",
                "--output",
                str(OUTPUT / "annotated.mp4"),
                "--jsonl",
                str(OUTPUT / "video.jsonl"),
            ]
        )
        == 0
    )
    capture = cv2.VideoCapture(str(OUTPUT / "annotated.mp4"))
    count = 0
    while capture.read()[0]:
        count += 1
    capture.release()
    assert count == 4
    # Repeat a genuinely detected decoded frame to verify backend ID persistence.
    capture = cv2.VideoCapture(str(video))
    capture.read()
    capture.read()
    ok, tracked_image = capture.read()
    capture.release()
    assert ok
    optimizer = OptimizationPipeline(
        PipelineConfig(hand_tracker=HandTrackerConfig(enabled=False, backend="none"))
    )
    config = load_config(OWNER / "config/standalone.yaml")
    config.device = "cpu"
    try:
        with YoloPipeline(config) as pipeline:
            prepared = FrameProcessor(PreprocessingConfig(max_width=160)).process(
                FramePacket(1, 1.0, image, 320, 240)
            )
            ai_before = prepared.image.copy()
            objects = pipeline.process(prepared)
            display = pipeline.render(prepared, objects)
            assert display.shape == image.shape and np.array_equal(
                ai_before, prepared.image
            )
            assert optimizer.process(prepared, objects).frame_id == 1
            assert objects.status in ("ok", "no_detection", "degraded")
            assert cv2.imwrite(str(OUTPUT / "integrated.png"), display)
            integrated_writer = cv2.VideoWriter(
                str(OUTPUT / "integrated.mp4"),
                cv2.VideoWriter_fourcc(*"mp4v"),
                10,
                (320, 240),
            )
            assert integrated_writer.isOpened()
            processor = FrameProcessor(PreprocessingConfig(max_width=160))
            try:
                for i in range(2, 6):
                    clean = np.roll(image, i * 10, axis=1)
                    prepared = processor.process(
                        FramePacket(i, float(i), clean, 320, 240)
                    )
                    ai_before = prepared.image.copy()
                    source_before = clean.copy()
                    objects = pipeline.process(prepared)
                    assert optimizer.process(prepared, objects).frame_id == i
                    integrated_writer.write(pipeline.render(prepared, objects))
                    assert np.array_equal(ai_before, prepared.image)
                    assert np.array_equal(source_before, clean)
            finally:
                integrated_writer.release()
            integrated_capture = cv2.VideoCapture(str(OUTPUT / "integrated.mp4"))
            integrated_count = 0
            while integrated_capture.read()[0]:
                integrated_count += 1
            integrated_capture.release()
            assert integrated_count == 4
            pipeline.reset()
            processor = FrameProcessor(PreprocessingConfig())
            ids = []
            for i in range(10, 14):
                frame = processor.process(
                    FramePacket(i, float(i), tracked_image, 320, 240)
                )
                tracked = pipeline.process(frame)
                ids.append([d.track_id for d in tracked.detections])
                assert cv2.imwrite(
                    str(OUTPUT / "tracked.png"), pipeline.render(frame, tracked)
                )
            assert any(any(t is not None for t in frame_ids) for frame_ids in ids), ids
    finally:
        optimizer.close()
    isolated = Path(tempfile.mkdtemp(prefix="orbita-module02-"))
    shutil.copytree(
        OWNER,
        isolated / "module02",
        ignore=shutil.ignore_patterns(
            ".verification", "__pycache__", "tests", "HAR.zip"
        ),
    )
    shutil.copy2(photo, isolated / "input.png")
    guard = """
import importlib.abc,sys,socket
class Guard(importlib.abc.MetaPathFinder):
 def find_spec(self,fullname,*args):
  if fullname.split('.')[0] in {'shared','perception','optimization','integration','procedure','FSM','GUI','alerts'}:
   raise AssertionError('forbidden import: '+fullname)
sys.meta_path.insert(0,Guard())
def reject(*args,**kwargs): raise AssertionError('network attempted')
socket.socket.connect=reject
socket.socket.sendto=reject
socket.getaddrinfo=reject
sys.path.insert(0,'module02')
import standalone
standalone.bootstrap()
from yolo.standalone_cli import main
raise SystemExit(main(['--source','input.png','--device','cpu','--no-display','--output','isolated.png']))
"""
    result = subprocess.run(
        [sys.executable, "-c", guard],
        cwd=isolated,
        capture_output=True,
        text=True,
        timeout=90,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert (isolated / "isolated.png").is_file()
    summary = {
        "image": "PASS",
        "video_frames": count,
        "integrated": "PASS",
        "integrated_video_frames": integrated_count,
        "copied_standalone": "PASS",
        "isolated_directory": str(isolated),
        "outbound_network": "BLOCKED DURING VERIFICATION",
        "real_tracker_ids": ids,
        "accuracy_fps_latency": "Not measured",
    }
    (OUTPUT / "summary.json").write_text(
        json.dumps(summary, indent=2), encoding="utf-8"
    )
    print(json.dumps(summary), flush=True)


if __name__ == "__main__":
    verify()
