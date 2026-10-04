"""Fail on network attempts while exercising installed real local backends.

YOLO uses temporary RANDOM weights unless --weights and --classes are supplied.
This checks loading/inference/tracking plumbing, not object recognition accuracy.
Run each backend in a fresh process because audit hooks cannot be removed.
"""

import argparse
import json
import os
import sys
from pathlib import Path
from tempfile import TemporaryDirectory
from time import perf_counter


def run(args):
    os.environ["YOLO_AUTOINSTALL"] = "false"
    os.environ["YOLO_OFFLINE"] = "true"
    attempts = []

    def reject_network(event, details):
        if event in {"socket.connect", "socket.getaddrinfo", "socket.sendto"}:
            attempts.append(event)
            raise RuntimeError(f"offline check rejected {event}")

    sys.addaudithook(reject_network)
    import numpy as np

    from shared.config import DetectorConfig, HandTrackerConfig

    image = np.zeros((240, 320, 3), np.uint8)
    with TemporaryDirectory(prefix="orbita-offline-") as temporary:
        if args.backend == "mediapipe":
            from optimization.hands.hand_tracker import MediaPipeHandTracker

            adapter = MediaPipeHandTracker(
                HandTrackerConfig(model_path=args.hand_model)
            )
        else:
            from yolo.inference.detector import UltralyticsYoloDetector

            weights, classes = args.weights, args.classes
            if (weights is None) != (classes is None):
                raise ValueError("supply --weights and --classes together")
            if weights is None:
                import ultralytics
                import yaml
                from ultralytics import YOLO

                architecture = (
                    Path(ultralytics.__file__).parent / "cfg/models/11/yolo11.yaml"
                )
                model = YOLO(str(architecture), task="detect")
                weights, classes = (
                    Path(temporary) / "random.pt",
                    Path(temporary) / "classes.yaml",
                )
                model.save(weights)
                classes.write_text(
                    yaml.safe_dump(
                        {
                            "classes": [
                                {"id": i, "name": name}
                                for i, name in model.names.items()
                            ]
                        }
                    )
                )
            adapter = UltralyticsYoloDetector(
                DetectorConfig(
                    model_path=weights,
                    classes_path=classes,
                    device="cpu",
                    tracking=args.tracking,
                    tracker_path=Path("configs/yolo_tracker.yaml"),
                )
            )
        counts, timings = [], []
        try:
            adapter.initialize()
            for timestamp in [0.0, 0.033, 0.067]:
                started = perf_counter()
                observations = (
                    adapter.track(image, timestamp_s=timestamp)
                    if args.backend == "mediapipe"
                    else adapter.detect(image)
                )
                timings.append((perf_counter() - started) * 1000)
                counts.append(len(observations))
        finally:
            adapter.close()
    if attempts:
        raise RuntimeError(
            f"network attempted even if backend caught rejection: {attempts}"
        )
    print(
        json.dumps(
            {
                "backend": args.backend,
                "tracking": args.tracking,
                "synthetic_weights": args.backend == "yolo" and args.weights is None,
                "observations_per_frame": counts,
                "network_attempts": len(attempts),
                "inference_ms": timings,
            }
        )
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("backend", choices=["mediapipe", "yolo"])
    parser.add_argument(
        "--hand-model", type=Path, default=Path("models/hand_landmarker.task")
    )
    parser.add_argument("--weights", type=Path)
    parser.add_argument("--classes", type=Path)
    parser.add_argument("--tracking", action="store_true")
    run(parser.parse_args())
