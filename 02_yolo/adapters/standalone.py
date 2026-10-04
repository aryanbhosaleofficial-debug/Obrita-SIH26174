"""OpenCV BGR -> Module 02 input. No Module 01 preprocessing dependency."""

import math

import numpy as np
from yolo.core.contracts import InputFrame, SourceFrame


def adapt_image(
    image,
    frame_id=0,
    timestamp_s=0.0,
    *,
    source_id="standalone",
    session_id="default",
    reset_required=False,
):
    if (
        not isinstance(image, np.ndarray)
        or image.dtype != np.uint8
        or image.ndim != 3
        or image.shape[2] != 3
        or min(image.shape[:2]) < 1
    ):
        raise ValueError("input source requires nonempty uint8 HxWx3 BGR")
    if type(frame_id) is not int or frame_id < 0:
        raise ValueError("frame_id must be a nonnegative integer")
    if (
        isinstance(timestamp_s, bool)
        or not isinstance(timestamp_s, (int, float))
        or not math.isfinite(timestamp_s)
    ):
        raise ValueError("timestamp_s must be finite")
    h, w = image.shape[:2]
    source = SourceFrame(frame_id, timestamp_s, image, w, h, source_id, session_id)
    return InputFrame(image, 1.0, 1.0, source, reset_required=reset_required)
