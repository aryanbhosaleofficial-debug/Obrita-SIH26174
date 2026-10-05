"""Offline Module 04 runner: synthetic scene, local image, or local video."""

import argparse
import json
import logging
import sys
from contextlib import nullcontext
from dataclasses import asdict
from pathlib import Path

import cv2
import numpy as np

from .boundary_pipeline import BoundaryPipeline

logger = logging.getLogger(__name__)


def frames(args):
    if args.synthetic:
        for index in range(args.frames):
            image = np.zeros((120, 160, 3), np.uint8)
            cv2.rectangle(
                image, (30 + index % 10, 35), (85 + index % 10, 85), (255, 255, 255), -1
            )
            yield index, index / 30, image
    elif args.image:
        image = cv2.imread(str(args.image))
        if image is None:
            raise ValueError(f"could not read image: {args.image}")
        yield 0, 0.0, image
    else:
        capture = cv2.VideoCapture(str(args.video))
        try:
            if not capture.isOpened():
                raise ValueError(f"could not open video: {args.video}")
            fps = float(capture.get(cv2.CAP_PROP_FPS))
            if not np.isfinite(fps) or fps <= 0:
                raise ValueError("video must provide a finite positive FPS")
            for index in range(args.frames):
                ok, image = capture.read()
                if not ok:
                    break
                yield index, index / fps, image
        finally:
            capture.release()


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--synthetic", action="store_true")
    source.add_argument("--image", type=Path)
    source.add_argument("--video", type=Path)
    parser.add_argument("--frames", type=int, default=5)
    parser.add_argument("--config", type=Path, help="optional existing boundary YAML")
    parser.add_argument(
        "--roi", type=int, nargs=4, metavar=("X", "Y", "WIDTH", "HEIGHT")
    )
    parser.add_argument("--output", type=Path)
    parser.add_argument("--debug", action="store_true")
    parser.add_argument(
        "--rack-valid",
        action="store_true",
        help="caller asserts a valid local rack reference; performs no calibration",
    )
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.DEBUG if args.debug else logging.WARNING)
    try:
        if args.frames <= 0:
            raise ValueError("--frames must be positive")
        if args.output and any(
            p is not None and p.resolve() == args.output.resolve()
            for p in (args.image, args.video, args.config)
        ):
            raise ValueError("--output must differ from input/config paths")
        pipeline = (
            BoundaryPipeline.from_yaml(args.config)
            if args.config
            else BoundaryPipeline()
        )
        destination = (
            args.output.open("w", encoding="utf-8")
            if args.output
            else nullcontext(sys.stdout)
        )
        with destination as stream:
            for fid, timestamp, image in frames(args):
                packet = pipeline.process(
                    image,
                    fid,
                    timestamp,
                    roi=tuple(args.roi) if args.roi else None,
                    rack_valid=args.rack_valid,
                )
                stream.write(json.dumps(asdict(packet), allow_nan=False) + "\n")
        return 0
    except (OSError, ValueError, TypeError, cv2.error) as exc:
        logger.error("Boundary runner failed: %s", exc)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
