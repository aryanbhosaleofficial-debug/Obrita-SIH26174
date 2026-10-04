"""Bounded sampled JPEG keyframes, detached from mutable AI input arrays."""

from collections import deque
from dataclasses import dataclass

import cv2
import numpy as np


@dataclass(frozen=True)
class Keyframe:
    frame_id: int
    timestamp_s: float
    jpeg: bytes
    observations: tuple


class TemporalBuffer:
    def __init__(self, config):
        self.config = config
        self.frames = deque(maxlen=config.capacity)
        self._count = 0

    def append(self, image, objects):
        sampled = self._count % self.config.sample_every_frames == 0
        self._count += 1
        if not sampled:
            return
        if self.frames and (
            objects.frame_id <= self.frames[-1].frame_id
            or objects.timestamp_s < self.frames[-1].timestamp_s
        ):
            self.clear()
        h, w = image.shape[:2]
        factor = min(1.0, self.config.max_image_side / max(h, w))
        small = (
            cv2.resize(image, (max(1, round(w * factor)), max(1, round(h * factor))))
            if factor < 1
            else image
        )
        ok, encoded = cv2.imencode(".jpg", small, [cv2.IMWRITE_JPEG_QUALITY, 75])
        if not ok or encoded.nbytes > 1024 * 1024:
            raise ValueError("semantic keyframe encoding failed or exceeds 1 MiB")
        observations = tuple(
            (d.class_name, d.track_id, d.confidence, d.bbox_xyxy)
            for d in objects.detections
        )
        self.frames.append(
            Keyframe(
                objects.frame_id, objects.timestamp_s, encoded.tobytes(), observations
            )
        )

    def select(self):
        frames = list(self.frames)
        if len(frames) <= self.config.keyframes:
            return tuple(frames)
        indexes = np.linspace(0, len(frames) - 1, self.config.keyframes, dtype=int)
        return tuple(frames[i] for i in indexes)

    def clear(self):
        self.frames.clear()
        self._count = 0
