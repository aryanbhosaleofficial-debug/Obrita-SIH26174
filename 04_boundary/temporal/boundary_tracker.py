"""Bounded single-target geometry history; BoundaryStateClassifier owns states."""

import math
from collections import deque
from dataclasses import dataclass, field


@dataclass
class BoundaryTrack:
    boundary_id: str = "boundary_01"
    history: deque = field(default_factory=lambda: deque(maxlen=20))
    missed: int = 0
    max_missing_frames: int = 2

    def mark_missing(self, count=1):
        self.missed = min(self.max_missing_frames + 1, self.missed + count)
        if self.missed > self.max_missing_frames:
            self.history.clear()

    def update(
        self, contour=None, centroid=None, frame_id=None, timestamp=None, confidence=0.0
    ):
        if contour is None or centroid is None:
            self.mark_missing()
            return {
                "tracked": False,
                "tracking_confidence": 0.0,
                "boundary_id": self.boundary_id,
                "current_centroid": None,
            }
        previous = self.history[-1] if self.history else None
        movement = math.dist(previous["centroid"], centroid) if previous else 0.0
        self.history.append(
            {
                "contour": contour,
                "centroid": tuple(centroid),
                "frame_id": frame_id,
                "timestamp": timestamp,
                "confidence": float(confidence),
            }
        )
        self.missed = 0
        return {
            "tracked": previous is not None,
            "tracking_confidence": float(confidence) * (1.0 if previous else 0.75),
            "boundary_id": self.boundary_id,
            "previous_centroid": previous["centroid"] if previous else None,
            "current_centroid": tuple(centroid),
            "movement": movement,
        }

    def reset(self):
        self.history.clear()
        self.missed = 0


class BoundaryTracker(BoundaryTrack):
    pass
