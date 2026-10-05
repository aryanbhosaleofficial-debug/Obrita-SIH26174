"""Standalone live preview: camera/video/image -> PoseFrame (+ optional YOLO) -> overlay.

    python -m 06_pose_tracking --camera 0
    python -m 06_pose_tracking --camera 0 --yolo
    python 06_pose_tracking/standalone.py --source clip.mp4 --no-display --jsonl pose.jsonl

Keys: Q / ESC quit, R reset tracker state. Runs fully offline; needs no
Boundary/HAR/FSM/GUI. Both branches consume the SAME PreparedFrame.
"""

from __future__ import annotations

import argparse
import json
import logging
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict
from pathlib import Path
from time import perf_counter

import cv2
from pose_tracking.config import DEFAULT_CONFIG_PATH, MODULE_ROOT, load_config
from pose_tracking.sources import (
    IMAGE_SUFFIXES,
    LatestFrameCamera,
    SourceError,
    file_frames,
)
from pose_tracking.tracker import PoseHandTracker
from pose_tracking.visualization import render_overlay

from perception.core import FrameProcessor
from shared.config import ConfigurationError
from shared.errors import InitializationError
from shared.schemas.frame_packet import FramePacket

LOGGER = logging.getLogger("pose_tracking.cli")
WINDOW = "ORBITA Module 06 - Pose & Hands"
DEFAULT_YOLO_CONFIG = MODULE_ROOT.parent / "02_yolo" / "config" / "standalone.yaml"
CAMERA_TIMEOUT_S = 2.0
CAMERA_MAX_TIMEOUTS = 3


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--camera", type=int, help="local camera index, e.g. 0")
    source.add_argument("--source", type=Path, help="local video or image file")
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG_PATH)
    parser.add_argument(
        "--yolo", action="store_true", help="also run Module 02 object boxes"
    )
    parser.add_argument("--yolo-config", type=Path, default=DEFAULT_YOLO_CONFIG)
    parser.add_argument(
        "--mirror", action="store_true", help="selfie view: flip before inference"
    )
    parser.add_argument(
        "--no-smoothing", action="store_true", help="publish raw model landmarks"
    )
    parser.add_argument("--camera-width", type=int)
    parser.add_argument("--camera-height", type=int)
    parser.add_argument("--no-display", action="store_true")
    parser.add_argument(
        "--output", type=Path, help="annotated .mp4 (stream) or image file"
    )
    parser.add_argument("--jsonl", type=Path, help="write one PoseFrame per line")
    parser.add_argument("--max-frames", type=int)
    return parser


def create_yolo(path: Path):
    """Module 02's canonical SIH stage, with its optional VLM worker disabled."""
    from yolo.config import load_config as load_yolo_config
    from yolo.pipeline import YoloPipeline
    from yolo.semantic.contracts import SemanticConfig

    pipeline = YoloPipeline(
        load_yolo_config(path), semantic_config=SemanticConfig(enabled=False)
    )
    pipeline.initialize()
    return pipeline


def _camera_frames(camera: LatestFrameCamera):
    timeouts = 0
    while True:
        frame = camera.read(CAMERA_TIMEOUT_S)
        if frame is None:
            timeouts += 1
            LOGGER.warning("no camera frame for %.1f s", CAMERA_TIMEOUT_S)
            if timeouts >= CAMERA_MAX_TIMEOUTS:
                raise SourceError("camera stopped delivering frames")
            continue
        timeouts = 0
        yield frame


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    logging.basicConfig(
        level=logging.INFO, format="%(levelname)s %(name)s: %(message)s"
    )
    tracker = yolo = camera = writer = jsonl = executor = None
    shown = False
    try:
        if args.max_frames is not None and args.max_frames < 1:
            raise ValueError("--max-frames must be positive")
        overrides = {"input_mirrored": True} if args.mirror else {}
        if args.no_smoothing:
            overrides["smoothing_alpha"] = 1.0
        config = load_config(args.config, **overrides)
        tracker = PoseHandTracker(config)
        tracker.initialize()  # models load once, here
        notes: list[str] = []
        if args.yolo:
            try:
                yolo = create_yolo(args.yolo_config)
                executor = ThreadPoolExecutor(
                    max_workers=1, thread_name_prefix="module06-yolo"
                )
            except Exception as exc:  # noqa: BLE001 -- pose preview continues without boxes
                LOGGER.error("YOLO unavailable, continuing pose-only: %s", exc)
                notes.append("YOLO: unavailable (see log)")
        if args.camera is not None:
            camera = LatestFrameCamera(
                args.camera, width=args.camera_width, height=args.camera_height
            )
            frames = _camera_frames(camera)
            source_id = f"camera_{args.camera}"
            single_image = False
        else:
            frames = file_frames(args.source)
            source_id = args.source.name
            single_image = args.source.suffix.lower() in IMAGE_SUFFIXES
        if args.output:
            suffix = args.output.suffix.lower()
            if single_image != (suffix in IMAGE_SUFFIXES) or (
                not single_image and suffix != ".mp4"
            ):
                raise ValueError("--output must be an image for image input, else .mp4")
        if args.jsonl:
            jsonl = args.jsonl.open("w", encoding="utf-8")

        core = FrameProcessor()  # Module 01: validation, ordering, source retention
        fps = None
        last_tick = None
        for count, frame in enumerate(frames, start=1):
            image = cv2.flip(frame.image, 1) if args.mirror else frame.image
            h, w = image.shape[:2]
            packet = FramePacket(
                frame.frame_id,
                frame.timestamp_s,
                image,
                w,
                h,
                source_id=source_id,
                dropped_frames_before=frame.dropped_frames_before,
            )
            prepared = core.process(packet)
            pending = executor.submit(yolo.process, prepared) if executor else None
            pose = tracker.process(prepared)  # same PreparedFrame as YOLO
            objects = pending.result() if pending else None

            now = perf_counter()
            if last_tick is not None:
                instant = 1.0 / max(now - last_tick, 1e-6)
                fps = instant if fps is None else 0.9 * fps + 0.1 * instant
            last_tick = now

            if jsonl:
                jsonl.write(json.dumps(asdict(pose)) + "\n")
            if not args.no_display or args.output:
                display = render_overlay(
                    prepared.source.image, pose, objects, fps=fps, extra_lines=notes
                )
                if args.output and single_image:
                    if not cv2.imwrite(str(args.output), display):
                        raise OSError(f"cannot write {args.output}")
                elif args.output:
                    if writer is None:
                        writer = cv2.VideoWriter(
                            str(args.output),
                            cv2.VideoWriter.fourcc(*"mp4v"),
                            30.0,
                            (w, h),
                        )
                        if not writer.isOpened():
                            raise OSError(f"cannot open {args.output}")
                    if display.shape[:2] == (h, w):
                        writer.write(display)
                if not args.no_display:
                    cv2.imshow(WINDOW, display)
                    shown = True
                    key = cv2.waitKey(0 if single_image else 1) & 0xFF
                    if key in (27, ord("q"), ord("Q")):
                        break
                    if key in (ord("r"), ord("R")):
                        tracker.reset()
                        if yolo is not None:
                            yolo.reset()
                        LOGGER.info("tracker state reset at frame %d", pose.frame_id)
                    if cv2.getWindowProperty(WINDOW, cv2.WND_PROP_VISIBLE) < 1:
                        break
            if args.max_frames and count >= args.max_frames:
                break
        return 0
    except KeyboardInterrupt:
        return 0
    except (
        ConfigurationError,
        InitializationError,
        SourceError,
        OSError,
        ValueError,
        cv2.error,
    ) as exc:
        LOGGER.error("Module 06 stopped [%s]: %s", type(exc).__name__, exc)
        return 2
    finally:
        if executor is not None:
            executor.shutdown(wait=True)
        if camera is not None:
            camera.close()
        if writer is not None:
            writer.release()
        if jsonl is not None:
            jsonl.close()
        for stage in (yolo, tracker):
            if stage is not None:
                stage.close()
        if shown:
            cv2.destroyAllWindows()
