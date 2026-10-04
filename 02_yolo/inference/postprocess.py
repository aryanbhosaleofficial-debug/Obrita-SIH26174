"""Ultralytics Results -> canonical observations in PREPARED-image pixels.

Ultralytics already reverses its internal letterbox and applies NMS. This module
does neither again; PreparedFrame.source_detection performs the sole remaining
prepared-to-source conversion in the stage.
"""

import math
from collections.abc import Iterable, Mapping
from numbers import Real
from typing import Any

import numpy as np
from yolo.inference.class_map import class_mapping

from shared.schemas.observations import BoundingBox, Detection


class BackendOutputError(ValueError):
    """A structurally inconsistent batch cannot be interpreted safely."""


def clamp_source_box(box: BoundingBox, width: int, height: int) -> BoundingBox:
    """Correct inverse-scale roundoff only, after authoritative restoration.

    Allow up to four floating-point ULPs at each source bound. Larger excursions
    indicate a contract/transform defect and fail instead of being concealed.
    """
    values = (box.x1, box.y1, box.x2, box.y2)
    limits = (width, height, width, height)
    for value, limit in zip(values, limits, strict=True):
        tolerance = 4 * math.ulp(float(limit))
        if not math.isfinite(value) or value < -tolerance or value > limit + tolerance:
            raise BackendOutputError("restored box materially exceeds source bounds")
    corrected = BoundingBox(
        *(
            float(min(limit, max(0.0, value)))
            for value, limit in zip(values, limits, strict=True)
        )
    )
    if corrected.x1 >= corrected.x2 or corrected.y1 >= corrected.y2:
        raise BackendOutputError("restored box has no positive area")
    return corrected


def _array(value: Any) -> np.ndarray:
    if hasattr(value, "cpu"):
        value = value.cpu()
    if hasattr(value, "numpy"):
        value = value.numpy()
    return np.asarray(value)


def _number(value: Any) -> bool:
    return (
        isinstance(value, Real)
        and not isinstance(value, (bool, np.bool_))
        and math.isfinite(value)
    )


def parse_results(
    results: Iterable[Any],
    shape: tuple[int, int],
    names: Mapping[int, str] | None,
    tracking: bool,
) -> tuple[list[Detection], int]:
    """Preserve valid rows/order; count invalid rows; reject structural corruption.

    Invalid class/track IDs are never rounded/truncated. Unknown classes are
    discarded with a count that the adapter exposes as a structured warning.
    A single input ndarray must not unexpectedly produce a multi-image batch.
    """
    rows = iter(results)
    result = next(rows, None)
    if result is None:
        return [], 0
    if next(rows, None) is not None:
        raise BackendOutputError("single prepared image produced multiple YOLO results")
    if hasattr(result, "orig_shape") and tuple(result.orig_shape) != shape:
        raise BackendOutputError("YOLO result orig_shape differs from prepared image")
    boxes = result.boxes
    if boxes is None:
        return [], 0
    reported_names = class_mapping(result.names)
    if names is None:  # compatibility for explicitly injected private model fixtures
        names = reported_names
    elif reported_names != names:
        raise BackendOutputError(
            "YOLO per-frame class mapping differs from validated model mapping"
        )
    coordinates, scores, classes = (
        _array(boxes.xyxy),
        _array(boxes.conf),
        _array(boxes.cls),
    )
    ids = _array(boxes.id) if tracking and boxes.id is not None else None
    count = len(coordinates) if coordinates.ndim else 0
    if (
        coordinates.shape != (count, 4)
        or scores.shape != (count,)
        or classes.shape != (count,)
        or (ids is not None and ids.shape != (count,))
    ):
        raise BackendOutputError(
            "YOLO box/score/class/ID arrays have inconsistent shapes"
        )
    output, invalid = [], 0
    for index in range(count):
        coords, score, cid = coordinates[index], scores[index], classes[index]
        tid = ids[index] if ids is not None else None
        if (
            not all(_number(v) for v in coords)
            or not _number(score)
            or not 0 <= score <= 1
            or not _number(cid)
            or cid < 0
            or cid != int(cid)
            or int(cid) not in names
            or (tid is not None and (not _number(tid) or tid < 0 or tid != int(tid)))
        ):
            invalid += 1
            continue
        output.append(
            Detection(
                int(cid),
                names[int(cid)],
                float(score),
                BoundingBox(*(float(v) for v in coords)),
                int(tid) if tid is not None else None,
            )
        )
    return output, invalid
