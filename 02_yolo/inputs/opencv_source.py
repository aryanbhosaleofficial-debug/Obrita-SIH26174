"""OpenCV camera, local video and image reader with deterministic cleanup."""

from pathlib import Path
from time import monotonic

import cv2


class InputSourceError(RuntimeError):
    pass


class OpenCVSource:
    def __init__(self, source):
        text = str(source)
        self.source = int(text) if text.isdecimal() else text
        self.capture = None
        self.image = None
        self.fps = 30.0
        if isinstance(self.source, str):
            if not Path(self.source).is_file():
                raise InputSourceError(f"local source file not found: {self.source}")
            if Path(self.source).suffix.lower() in {
                ".jpg",
                ".jpeg",
                ".png",
                ".bmp",
                ".tif",
                ".tiff",
                ".webp",
            }:
                self.image = cv2.imread(self.source)
                if self.image is None:
                    raise InputSourceError(f"cannot decode image: {self.source}")
        if self.image is None:
            self.capture = cv2.VideoCapture(self.source)
            if not self.capture.isOpened():
                self.close()
                raise InputSourceError(f"cannot open input source: {self.source}")
            fps = self.capture.get(cv2.CAP_PROP_FPS)
            if 0 < fps <= 240:
                self.fps = fps

    def __iter__(self):
        if self.image is not None:
            yield 0, 0.0, self.image
            return
        frame_id = 0
        started = monotonic()
        while True:
            ok, image = self.capture.read()
            if not ok:
                if frame_id == 0 or isinstance(self.source, int):
                    raise InputSourceError("camera/source frame read failed")
                break  # OpenCV does not reliably distinguish EOF and corrupt video.
            timestamp = (
                monotonic() - started
                if isinstance(self.source, int)
                else frame_id / self.fps
            )
            yield frame_id, timestamp, image
            frame_id += 1

    def close(self):
        if self.capture is not None:
            self.capture.release()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()
