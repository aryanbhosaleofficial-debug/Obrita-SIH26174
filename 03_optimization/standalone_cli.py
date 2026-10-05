"""Offline ObjectFrame replay; no camera, inference, or model initialization."""

import argparse
import json
import logging
import sys
from contextlib import nullcontext
from dataclasses import asdict
from pathlib import Path

from optimization.config import load_config
from optimization.optimizer import OptimizationSequence

from shared.diagnostics import Diagnostic, NoticeCode, WarningCode
from shared.enums.module_status import ModuleStatus
from shared.schemas.object_frame import ObjectFrame, ReferenceAnchor
from shared.schemas.observations import BoundingBox, Detection, MotionState, Point2D

logger = logging.getLogger(__name__)


def decode_object_frame(value: dict) -> ObjectFrame:
    """Decode canonical asdict(ObjectFrame), or Module 02 CLI's 'objects' envelope."""
    if not isinstance(value, dict):
        raise TypeError("expected an ObjectFrame JSON object")
    data = dict(value.get("objects", value))
    data["status"] = ModuleStatus(data.get("status", "ok"))
    detections = []
    for raw in data.get("detections", []):
        d = dict(raw)
        d["bbox"] = BoundingBox(**d["bbox"])
        d["motion"] = MotionState(d.get("motion", "unknown"))
        if d.get("reference_polygon") is not None:
            d["reference_polygon"] = tuple(Point2D(**p) for p in d["reference_polygon"])
        if d.get("velocity_reference_frame") is not None:
            d["velocity_reference_frame"] = Point2D(**d["velocity_reference_frame"])
        detections.append(Detection(**d))
    data["detections"] = detections
    anchors = []
    for raw in data.get("reference_anchors", []):
        a = dict(raw)
        a["bbox_xyxy"] = tuple(a["bbox_xyxy"])
        a["keypoints_px"] = [tuple(p) for p in a.get("keypoints_px", [])]
        anchors.append(ReferenceAnchor(**a))
    data["reference_anchors"] = anchors
    for name, code_type in (("warnings", WarningCode), ("notices", NoticeCode)):
        data[name] = [
            Diagnostic(code_type(d["code"]), d.get("details", {}))
            for d in data.get(name, [])
        ]
    return ObjectFrame(**data)


def replay(path: Path):
    if path.suffix.lower() == ".jsonl":
        with path.open(encoding="utf-8") as stream:
            for number, line in enumerate(stream, 1):
                if not line.strip():
                    continue
                try:
                    yield decode_object_frame(json.loads(line))
                except (ValueError, TypeError, KeyError) as exc:
                    raise ValueError(f"{path}: line {number}: {exc}") from exc
    else:
        with path.open(encoding="utf-8") as stream:
            data = json.load(stream)
        for value in data if isinstance(data, list) else [data]:
            yield decode_object_frame(value)


def synthetic(config):
    # Confirm, tolerate the full allowed gap, reacquire, then expire.
    present = (
        [True] * config.detection_min_frames
        + [False] * config.max_missing_frames
        + [True]
        + [False] * (config.max_missing_frames + 1)
    )
    for frame_id, seen in enumerate(present):
        yield ObjectFrame(
            frame_id,
            frame_id / 30,
            320,
            240,
            [Detection(0, "sample_object", 0.9, BoundingBox(100, 80, 180, 160), 7)]
            if seen
            else [],
            source_id="synthetic",
            session_id="optimization_demo",
        )


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--synthetic", action="store_true")
    source.add_argument(
        "--input", type=Path, help="ObjectFrame JSON/JSONL or Module 02 JSONL"
    )
    parser.add_argument(
        "--config",
        type=Path,
        default=Path(__file__).resolve().parents[1] / "configs/optimization.yaml",
    )
    parser.add_argument("--output", type=Path, help="output JSONL (default: stdout)")
    parser.add_argument("--debug", action="store_true")
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.DEBUG if args.debug else logging.WARNING)
    try:
        if args.input and args.output and args.input.resolve() == args.output.resolve():
            raise ValueError("--output must differ from --input")
        config = load_config(args.config)
        optimizer = OptimizationSequence(config)
        frames = synthetic(config) if args.synthetic else replay(args.input)
        destination = (
            args.output.open("w", encoding="utf-8")
            if args.output
            else nullcontext(sys.stdout)
        )
        with destination as stream:
            for frame in frames:
                output = optimizer.process(frame)
                stream.write(json.dumps(asdict(output), allow_nan=False) + "\n")
        return 0
    except (OSError, ValueError, TypeError, KeyError) as exc:
        logger.error("Optimization replay failed: %s", exc)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
