"""Frame sources for the standalone demo.

``LatestFrameCamera`` keeps only the newest captured frame (a one-slot buffer):
when inference is slower than the camera, stale frames are overwritten rather
than queued, so latency stays bounded. Overwritten frames show up as frame_id
gaps plus ``dropped_frames_before``, which Module 01 already accounts for.
"""

from __future__ import annotations

import logging
from collections.abc import Callable, Iterator
from dataclasses import dataclass
from pathlib import Path
from threading import Condition, Thread
from time import monotonic, perf_counter

import cv2
import numpy as np

LOGGER = logging.getLogger("pose_tracking.sources")
IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png", ".bmp", ".tif", ".tiff", ".webp"}


class SourceError(RuntimeError):
    pass


@dataclass(frozen=True)
class CapturedFrame:
    frame_id: int
    timestamp_s: float
    image: np.ndarray
    dropped_frames_before: int = 0


class LatestFrameCamera:
    """Background reader thread + one-slot latest-frame buffer."""

    def __init__(
        self,
        index: int,
        *,
        width: int | None = None,
        height: int | None = None,
        read_failure_limit: int = 30,
        capture_factory: Callable[[int], object] = cv2.VideoCapture,
    ):
        self._capture = capture_factory(index)
        if not self._capture.isOpened():
            self._capture.release()
            raise SourceError(f"cannot open camera {index}")
        if width:
            self._capture.set(cv2.CAP_PROP_FRAME_WIDTH, width)
        if height:
            self._capture.set(cv2.CAP_PROP_FRAME_HEIGHT, height)
        self._capture.set(cv2.CAP_PROP_BUFFERSIZE, 1)  # best effort; driver may ignore
        self.read_failure_limit = read_failure_limit
        self._cond = Condition()
        self._slot: tuple[int, float, np.ndarray] | None = None
        self._last_delivered = -1
        self._error: str | None = None
        self._stopped = False
        self._started = perf_counter()
        self._thread = Thread(target=self._run, name="pose-camera", daemon=True)
        self._thread.start()

    def _run(self) -> None:
        captured = 0
        failures = 0
        while True:
            with self._cond:
                if self._stopped:
                    return
            ok, image = self._capture.read()
            # perf_counter, not monotonic(): on Windows monotonic() ticks every
            # ~15.6 ms, so consecutive 30 FPS captures could share a timestamp and
            # be rejected downstream as non-monotonic.
            timestamp = perf_counter() - self._started
            with self._cond:
                if self._stopped:
                    return
                if ok and image is not None:
                    failures = 0
                    if self._slot is not None and timestamp <= self._slot[1]:
                        timestamp = self._slot[1] + 1e-6  # keep strictly increasing
                    self._slot = (captured, timestamp, image)  # overwrite: never queue
                    captured += 1
                else:
                    failures += 1
                    if failures >= self.read_failure_limit:
                        self._error = f"camera read failed {failures} times in a row"
                        self._cond.notify_all()
                        return
                self._cond.notify_all()

    def read(self, timeout_s: float = 2.0) -> CapturedFrame | None:
        """Newest frame not yet delivered; None on timeout. Raises on camera failure."""
        deadline = monotonic() + timeout_s
        with self._cond:
            while True:
                if self._slot is not None and self._slot[0] > self._last_delivered:
                    frame_id, timestamp, image = self._slot
                    dropped = frame_id - self._last_delivered - 1
                    self._last_delivered = frame_id
                    return CapturedFrame(frame_id, timestamp, image, dropped)
                if self._error is not None:
                    raise SourceError(self._error)
                remaining = deadline - monotonic()
                if remaining <= 0 or self._stopped:
                    return None
                self._cond.wait(remaining)

    def close(self) -> None:
        with self._cond:
            self._stopped = True
            self._cond.notify_all()
        self._thread.join(timeout=2.0)
        self._capture.release()


def file_frames(path: Path) -> Iterator[CapturedFrame]:
    """Sequential local image/video frames (no dropping; timestamps from FPS)."""
    if not path.is_file():
        raise SourceError(f"local source file not found: {path}")
    if path.suffix.lower() in IMAGE_SUFFIXES:
        image = cv2.imread(str(path))
        if image is None:
            raise SourceError(f"cannot decode image: {path}")
        yield CapturedFrame(0, 0.0, image)
        return
    capture = cv2.VideoCapture(str(path))
    try:
        if not capture.isOpened():
            raise SourceError(f"cannot open video: {path}")
        fps = capture.get(cv2.CAP_PROP_FPS)
        fps = fps if 0 < fps <= 240 else 30.0
        frame_id = 0
        while True:
            ok, image = capture.read()
            if not ok:
                if frame_id == 0:
                    raise SourceError(f"no readable frames in {path}")
                return
            yield CapturedFrame(frame_id, frame_id / fps, image)
            frame_id += 1
    finally:
        capture.release()
