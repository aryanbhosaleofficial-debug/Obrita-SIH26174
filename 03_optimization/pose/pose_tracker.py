"""Optional body pose; local helper model only, disabled unless explicitly injected."""

from typing import Protocol

import numpy as np

from shared.schemas.observations import PoseObservation


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


class MediaPipePoseTracker:
    """Adapt the existing Module 06 backend to Module 03's observation interface.

    Only the body model runs here; Module 03's hand tracker already owns hands.
    Model scores are kept optional, and no relative depth is claimed as metric.
    """

    def __init__(self, config, backend=None):
        from dataclasses import replace

        self.config = replace(config, body_enabled=True, hands_enabled=False).validate()
        self.backend = backend
        self._initialized = False

    def initialize(self):
        from shared.errors import InitializationError

        if self._initialized:
            return
        path = self.config.pose_model_path
        if self.backend is None:
            if path is None or not path.is_file():
                raise InitializationError(
                    f"pose model file not found: {path}; provide --pose-model <local .task path> "
                    "or configure pose_model_path in --pose-config"
                )
            from pose_tracking.backends import MediaPipeLandmarkBackend

            self.backend = MediaPipeLandmarkBackend(self.config)
        self.backend.initialize()
        self._initialized = True

    def track_at(self, image, timestamp_s):
        from shared.schemas.observations import Point2D

        self.initialize()
        raw = self.backend.detect(image, timestamp_s)
        if not raw.body:
            return []
        height, width = image.shape[:2]
        scores = [v for p in raw.body for v in (p.visibility, p.presence) if v is not None]
        return [PoseObservation(
            [Point2D(p.x * width, p.y * height) for p in raw.body],
            min(scores) if scores else None,
        )]

    def close(self):
        self._initialized = False
        if self.backend is not None:
            self.backend.close()
