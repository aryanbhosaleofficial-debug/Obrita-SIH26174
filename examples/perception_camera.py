"""Optional external camera/video adapter; perception itself never owns capture."""

import argparse
from pathlib import Path
from time import monotonic

import cv2
from boundary.input.contract_validator import validate_boundary_input

from integration.chain import PerceptionChain
from shared.enums.module_status import ModuleStatus
from shared.schemas.frame_packet import FramePacket

ROOT = Path(__file__).resolve().parents[1]


def run(source: str, config: Path) -> None:
    capture = cv2.VideoCapture(int(source) if source.isdecimal() else source)
    try:
        if not capture.isOpened():
            raise RuntimeError(f"cannot open frame source: {source}")
        fps = capture.get(cv2.CAP_PROP_FPS)
        if not source.isdecimal() and fps <= 0:
            raise ValueError(
                "video must report a positive frame rate for timestamped replay"
            )
        with PerceptionChain.from_yaml(config) as pipeline:
            frame_id = 0
            while True:
                ok, image = capture.read()
                if not ok:
                    break
                height, width = image.shape[:2]
                packet = FramePacket(
                    frame_id,
                    monotonic() if source.isdecimal() else frame_id / fps,
                    image,
                    width,
                    height,
                    source_id=source,
                )
                result = pipeline.process(packet).optimization
                if result.status not in (
                    ModuleStatus.ERROR,
                    ModuleStatus.INVALID_INPUT,
                ):
                    validate_boundary_input(result, packet)
                print(result.frame_id, result.interactions, result.warnings)
                frame_id += 1
    finally:
        capture.release()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--source", default="0", help="camera index or local video path"
    )
    parser.add_argument(
        "--config", type=Path, default=ROOT / "configs/perception_demo.yaml"
    )
    args = parser.parse_args()
    run(args.source, args.config)
