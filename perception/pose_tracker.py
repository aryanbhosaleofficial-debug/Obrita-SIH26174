"""Optional body-pose extension point; no pose model loaded by default."""

from typing import Protocol

import numpy as np

from perception.contracts import PoseObservation


class PoseTracker(Protocol):
    def initialize(self) -> None: ...
    def track(self, image: np.ndarray) -> list[PoseObservation]: ...
    def close(self) -> None: ...


class NullPoseTracker:
    def initialize(self) -> None:
        pass

    def track(self, image: np.ndarray) -> list[PoseObservation]:
        return []

    def close(self) -> None:
        pass
