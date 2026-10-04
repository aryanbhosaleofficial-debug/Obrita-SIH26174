"""Run with python -m examples.perception_demo; no camera/models/network needed."""

import argparse
import json
from dataclasses import asdict
from pathlib import Path

import numpy as np

from perception import FramePacket, PerceptionPipeline
from perception.integration import to_object_frame
from perception.mocks import demo_backends

ROOT = Path(__file__).resolve().parents[1]


def run(frame_count: int = 8) -> None:
    detector, hands = demo_backends()
    with PerceptionPipeline.from_yaml(
        ROOT / "configs/perception_mock.yaml", detector=detector, hand_tracker=hands
    ) as pipeline:
        for frame_id in range(frame_count):
            image = np.zeros((240, 320, 3), dtype=np.uint8)
            packet = FramePacket(
                frame_id,
                frame_id / 30,
                image,
                width=320,
                height=240,
                source_id="synthetic",
            )
            result = pipeline.process(packet)
            # Existing object consumers can use this bridge. A future HAR layer
            # consumes result.interactions, confidence and coordinate validity.
            objects = to_object_frame(result)
            print(
                json.dumps(
                    {
                        "frame_id": result.frame_id,
                        "timestamp_s": result.timestamp_s,
                        "stable_objects": sum(d.is_stable for d in objects.detections),
                        "coordinate_frame_valid": result.coordinate_frame_valid,
                        "interactions": [asdict(i) for i in result.interactions],
                        "warnings": result.warnings,
                    }
                )
            )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--frames", type=int, default=8)
    args = parser.parse_args()
    if args.frames < 1:
        parser.error("--frames must be positive")
    run(args.frames)
