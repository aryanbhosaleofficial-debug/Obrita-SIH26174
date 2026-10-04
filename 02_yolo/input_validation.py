"""YOLO-specific boundary checks; no frame preparation or sequencing policy."""

import math
from numbers import Real

import numpy as np

from shared.schemas.prepared_frame import PreparedFrame


def input_error(prepared: PreparedFrame) -> str | None:
    """Check the prepared BGR image and reversible scale required by inference."""
    image, source = prepared.image, prepared.source
    if source is None:
        raise ValueError("PreparedFrame must retain its source")
    if not prepared.accepted:
        return "upstream frame was not accepted"
    if (
        not isinstance(image, np.ndarray)
        or image.dtype != np.uint8
        or image.ndim != 3
        or image.shape[2] != 3
        or min(image.shape[:2]) <= 0
    ):
        return "YOLO requires a nonempty prepared uint8 HxWx3 BGR image"
    for name, scale in (("scale_x", prepared.scale_x), ("scale_y", prepared.scale_y)):
        if (
            isinstance(scale, (bool, np.bool_))
            or not isinstance(scale, Real)
            or not math.isfinite(scale)
            or scale <= 0
        ):
            return f"{name} must be finite and positive"
    try:
        if source.width <= 0 or source.height <= 0:
            return "source dimensions must be positive"
        if not math.isclose(
            image.shape[1] / source.width, prepared.scale_x, rel_tol=1e-9
        ) or not math.isclose(
            image.shape[0] / source.height, prepared.scale_y, rel_tol=1e-9
        ):
            return "prepared scale disagrees with prepared/source dimensions"
    except (TypeError, ZeroDivisionError):
        return "source dimensions are not numeric"
    return None
