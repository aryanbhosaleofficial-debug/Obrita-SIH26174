"""Opt-in real CPU check, run as python -m yolo.tests.verify_real_offline.

Requires installed inference dependencies. Creates temporary RANDOM weights from
an installed architecture: verifies plumbing, not experiment detection accuracy.
Run in a fresh process because the network audit hook cannot be removed.
"""

import json
import os
import sys
from pathlib import Path
from tempfile import TemporaryDirectory


def main() -> None:
    os.environ["YOLO_AUTOINSTALL"] = "false"
    os.environ["YOLO_OFFLINE"] = "true"
    attempts = []

    def deny(event, args):
        if event in {"socket.connect", "socket.getaddrinfo", "socket.sendto"}:
            attempts.append(event)
            raise RuntimeError(f"offline verification rejected {event}")

    sys.addaudithook(deny)
    import cv2
    import numpy as np
    import torch
    import ultralytics
    import yaml
    from optimization.pipeline import OptimizationPipeline
    from ultralytics import YOLO
    from yolo.cli import main as cli_main
    from yolo.pipeline import YoloPipeline

    from perception.core import FrameProcessor
    from shared.config import (
        DetectorConfig,
        HandTrackerConfig,
        PipelineConfig,
        PreprocessingConfig,
    )
    from shared.enums.module_status import ModuleStatus
    from shared.schemas.frame_packet import FramePacket

    torch.manual_seed(0)
    with TemporaryDirectory(prefix="orbita-module02-offline-") as temp:
        root = Path(temp)
        architecture = Path(ultralytics.__file__).parent / "cfg/models/11/yolo11.yaml"
        model = YOLO(str(architecture), task="detect")
        weights = root / "random.pt"
        model.save(weights)
        classes = root / "classes.yaml"
        classes.write_text(
            yaml.safe_dump(
                {
                    "classes": [
                        {"id": i, "name": name} for i, name in model.names.items()
                    ]
                }
            ),
            encoding="utf-8",
        )
        config = DetectorConfig(
            model_path=weights,
            classes_path=classes,
            device="cpu",
            tracking=True,
            tracker_path=Path("configs/yolo_tracker.yaml"),
        )
        optimizer = OptimizationPipeline(
            PipelineConfig(
                hand_tracker=HandTrackerConfig(enabled=False, backend="none")
            )
        )
        processor = FrameProcessor(PreprocessingConfig(max_width=320))
        statuses, counts = [], []
        try:
            with YoloPipeline(config) as stage:
                model_identity = id(stage.detector._model)
                for i, (h, w) in enumerate([(240, 640), (240, 640), (640, 240)]):
                    image = np.zeros((h, w, 3), np.uint8)
                    packet = FramePacket(
                        i,
                        i / 30,
                        image,
                        w,
                        h,
                        source_id="offline-test",
                        session_id="real-local",
                    )
                    prepared = processor.process(packet)
                    objects = stage.process(prepared)
                    assert objects.status not in (
                        ModuleStatus.ERROR,
                        ModuleStatus.INVALID_INPUT,
                    ), objects.warnings
                    result = optimizer.process(prepared, objects)
                    assert (
                        result.frame_id == i
                        and result.timestamp_s == packet.timestamp_s
                    )
                    assert (
                        result.object_frame.image_width == w
                        and result.source_id == "offline-test"
                    )
                    assert id(stage.detector._model) == model_identity
                    counts.append(len(objects.detections))
                    statuses.append(objects.status.value)
        finally:
            optimizer.close()
        input_path = root / "input.png"
        assert cv2.imwrite(str(input_path), image)
        exit_code = cli_main(
            [
                "--input",
                str(input_path),
                "--weights",
                str(weights),
                "--classes",
                str(classes),
                "--device",
                "cpu",
                "--no-tracking",
            ]
        )
        assert exit_code == 0
    assert not attempts, attempts
    print(
        json.dumps(
            {
                "real_chain_frames": 3,
                "statuses": statuses,
                "observations_per_frame": counts,
                "network_attempts": len(attempts),
                "cli_exit": exit_code,
                "synthetic_random_weights": True,
                "ultralytics": ultralytics.__version__,
            }
        )
    )


if __name__ == "__main__":
    main()
