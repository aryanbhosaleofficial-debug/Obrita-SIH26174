"""Real module chain with injected synthetic observations and live ArUco pixels."""

import argparse
import json
from dataclasses import asdict
from pathlib import Path

from boundary.input.contract_validator import validate_boundary_input

from integration.chain import PerceptionChain
from integration.marker_scene import marker_board
from integration.mocks import demo_backends
from shared.schemas.frame_packet import FramePacket

ROOT = Path(__file__).resolve().parents[1]


def run(frame_count: int = 8) -> None:
    detector, hands = demo_backends()
    with PerceptionChain.from_yaml(
        ROOT / "configs/perception_mock.yaml", detector=detector, hand_tracker=hands
    ) as pipeline:
        for frame_id in range(frame_count):
            image = marker_board()
            packet = FramePacket(
                frame_id,
                frame_id / 30,
                image,
                400,
                400,
                source_id="synthetic",
                session_id="mock-demo",
            )
            stages = pipeline.process(packet)
            result = stages.optimization
            validate_boundary_input(result, stages.prepared.source)
            print(
                json.dumps(
                    {
                        "frame_id": result.frame_id,
                        "packets": [
                            type(stages.prepared).__name__,
                            type(stages.objects).__name__,
                            type(result).__name__,
                        ],
                        "status": result.status,
                        "reliable_for_temporal_reasoning": result.reliable_for_temporal_reasoning,
                        "reference": asdict(result.spatial.reference_frame),
                        "interactions": [asdict(i) for i in result.interactions],
                        "warnings": [asdict(w) for w in result.warnings],
                        "notices": [asdict(n) for n in result.notices],
                        "stage_timings_ms": result.stage_timings_ms,
                        "boundary_input_valid": True,
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
