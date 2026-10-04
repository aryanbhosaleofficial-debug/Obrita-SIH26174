"""Optional external camera/video adapter; perception itself never owns capture."""

import argparse
from pathlib import Path
from time import monotonic

import cv2

from perception import FramePacket, PerceptionPipeline

ROOT = Path(__file__).resolve().parents[1]


def run(source: str, config: Path) -> None:
    capture = cv2.VideoCapture(int(source) if source.isdecimal() else source)
    try:
        if not capture.isOpened():
            raise RuntimeError(f"cannot open frame source: {source}")
        with PerceptionPipeline.from_yaml(config) as pipeline:
            frame_id = 0
            while True:
                ok, image = capture.read()
                if not ok:
                    break
                height, width = image.shape[:2]
                packet = FramePacket(
                    frame_id, monotonic(), image, width, height, source_id=source
                )
                result = pipeline.process(packet)
                print(result.frame_id, result.interactions, result.warnings)
                frame_id += 1
    finally:
        capture.release()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--source", default="0", help="camera index or local video path"
    )
    parser.add_argument("--config", type=Path, default=ROOT / "configs/perception.yaml")
    args = parser.parse_args()
    run(args.source, args.config)
