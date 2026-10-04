"""Copy-only BGR preprocessing with reversible source-coordinate scaling."""

import math
from numbers import Integral, Real

import cv2
import numpy as np

from perception.config import PreprocessingConfig
from perception.contracts import (
    FramePacket,
)


class InvalidFrameError(ValueError):
    pass


from shared.schemas.prepared_frame import PreparedFrame

PreprocessedFrame = PreparedFrame


def preprocess(packet: FramePacket, config: PreprocessingConfig) -> PreprocessedFrame:
    """Accept uint8 HxWx3 BGR/RGB; reject mismatched metadata and bad timestamps."""
    image = packet.image
    if (
        not isinstance(image, np.ndarray)
        or image.dtype != np.uint8
        or image.ndim != 3
        or image.shape[2] != 3
        or min(image.shape[:2]) <= 0
    ):
        raise InvalidFrameError("expected a nonempty uint8 HxWx3 image")
    if (packet.height, packet.width) != image.shape[:2]:
        raise InvalidFrameError("frame dimensions disagree with metadata")
    if (
        isinstance(packet.frame_id, (bool, np.bool_))
        or not isinstance(packet.frame_id, Integral)
        or packet.frame_id < 0
    ):
        raise InvalidFrameError("frame_id must be a nonnegative integer")
    if (
        isinstance(packet.timestamp_s, bool)
        or not isinstance(packet.timestamp_s, Real)
        or not math.isfinite(packet.timestamp_s)
    ):
        raise InvalidFrameError("timestamp_s must be finite monotonic seconds")
    if not isinstance(packet.source_id, str) or not packet.source_id:
        raise InvalidFrameError("source_id must be nonempty")
    if packet.color_format not in ("BGR", "RGB"):
        raise InvalidFrameError("supported color formats are BGR and RGB")
    image = (
        cv2.cvtColor(image, cv2.COLOR_RGB2BGR)
        if packet.color_format == "RGB"
        else image
    )
    if config.max_width is not None and packet.width > config.max_width:
        new_height = max(1, round(packet.height * config.max_width / packet.width))
        image = cv2.resize(
            image, (config.max_width, new_height), interpolation=cv2.INTER_AREA
        )
    if config.equalize_luminance:
        lab = cv2.cvtColor(image, cv2.COLOR_BGR2LAB)
        lab[:, :, 0] = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8)).apply(
            lab[:, :, 0]
        )
        image = cv2.cvtColor(lab, cv2.COLOR_LAB2BGR)
    if image is packet.image:
        image = image.copy()
    return PreprocessedFrame(
        np.ascontiguousarray(image),
        image.shape[1] / packet.width,
        image.shape[0] / packet.height,
        source=packet,
    )
