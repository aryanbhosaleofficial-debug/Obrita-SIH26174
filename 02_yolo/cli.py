"""Local single-image smoke runner; application capture remains external."""

import argparse
import json
import logging
from dataclasses import asdict, replace
from pathlib import Path

import cv2
from yolo.config import load_config
from yolo.pipeline import YoloPipeline

from perception.core import FrameProcessor
from shared.config import ConfigurationError
from shared.enums.module_status import ModuleStatus
from shared.errors import InitializationError
from shared.schemas.frame_packet import FramePacket

ROOT = Path(__file__).resolve().parents[1]
LOGGER = logging.getLogger(__name__)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--input", type=Path, required=True, help="existing local image file"
    )
    parser.add_argument("--config", type=Path, default=ROOT / "configs/yolo.yaml")
    parser.add_argument(
        "--core-config", type=Path, default=ROOT / "configs/perception.yaml"
    )
    parser.add_argument("--weights", type=Path)
    parser.add_argument("--classes", type=Path)
    parser.add_argument("--device")
    parser.add_argument(
        "--tracking", action=argparse.BooleanOptionalAction, default=None
    )
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO)
    try:
        config = load_config(args.config)
        updates = {
            name: value
            for name, value in {
                "model_path": args.weights,
                "classes_path": args.classes,
                "device": args.device,
                "tracking": args.tracking,
            }.items()
            if value is not None
        }
        config = replace(config, **updates)
        if not args.input.is_file():
            raise ValueError(f"input image not found: {args.input}")
        image = cv2.imread(str(args.input))
        if image is None:
            raise ValueError(f"cannot decode local input image: {args.input}")
        source = FramePacket(
            0,
            0.0,
            image,
            image.shape[1],
            image.shape[0],
            source_id=str(args.input),
            session_id="yolo-smoke",
        )
        prepared = FrameProcessor.from_yaml(args.core_config).process(source)
        with YoloPipeline(config) as detector:
            output = detector.process(prepared)
        print(json.dumps(asdict(output)))
        return (
            1
            if output.status in (ModuleStatus.ERROR, ModuleStatus.INVALID_INPUT)
            else 0
        )
    except (ConfigurationError, InitializationError, OSError, ValueError) as exc:
        LOGGER.error("YOLO smoke failed: %s", exc)
        return 2
