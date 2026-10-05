"""Explicit inference-only substitute for offline contract demonstrations."""
from pose_tracking.backends import RawHand, RawLandmark, RawResult
import numpy as np


class SyntheticLandmarkBackend:
    """Deterministic body and two hands, then losses; no inference claim."""
    def initialize(self) -> None:
        self.count = 0

    def detect(self, image_bgr: np.ndarray, timestamp_s: float) -> RawResult:
        self.count += 1
        if self.count > 30 or self.count % 10 == 0:
            return RawResult()
        body = tuple(RawLandmark(.35 + .01 * (i % 7), .3 + .03 * (i // 7),
                                 0.0, .9, .9) for i in range(33))
        hands = tuple(RawHand(tuple(RawLandmark(x + .01 * (i % 5),
                                                .5 + .01 * (i // 5), 0.0)
                                       for i in range(21)), label, .95)
                      for x, label in ((.3, "Left"), (.6, "Right")))
        return RawResult(body, hands)

    def close(self) -> None:
        pass
