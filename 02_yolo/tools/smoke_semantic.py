"""Optional local-model smoke on synthetic chronological frames, no accuracy claim."""

import json
import sys
from dataclasses import asdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from standalone import bootstrap

bootstrap()

import cv2
import numpy as np
from yolo.core.contracts import BoundingBox, Detection
from yolo.core.contracts import DetectionFrame as ObjectFrame
from yolo.semantic.contracts import SemanticConfig
from yolo.semantic.qwen_verifier import QwenVerifier
from yolo.semantic.temporal_buffer import TemporalBuffer


def main():
    config = SemanticConfig(enabled=True, sample_every_frames=1, timeout_s=60)
    buffer = TemporalBuffer(config)
    for i in range(4):
        image = np.full((192, 256, 3), 210, np.uint8)
        x = 40 + i * 10
        cv2.rectangle(image, (x, 90), (x + 45, 135), (0, 0, 255), -1)
        buffer.append(
            image,
            ObjectFrame(
                i,
                float(i),
                256,
                192,
                [Detection(2, "red_box", 0.9, BoundingBox(x, 90, x + 45, 135), 1)],
            ),
        )
    verifier = QwenVerifier(config)
    print("Availability:", verifier.check_availability(), flush=True)
    result = verifier.verify(buffer.select(), 1, "track_displacement")
    print(json.dumps(asdict(result)), flush=True)
    return 0 if result.status == "READY" else 1


if __name__ == "__main__":
    raise SystemExit(main())
