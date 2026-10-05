"""Closed-contour Freeman edge directions: E, SE, S, SW, W, NW, N, NE.

Directions describe image coordinates only; they do not define physical up.
Runtime contours are dense OpenCV 8-connected pixel boundaries.
"""

import math
from collections.abc import Sequence

import numpy as np


def freeman_chain(contour: Sequence[Sequence[float]] | np.ndarray) -> list[int]:
    points = np.asarray(contour, dtype=float)
    if not points.size:
        return []
    if points.ndim != 2 or points.shape[1] != 2 or not np.isfinite(points).all():
        raise ValueError("contour must contain finite (n, 2) XY points")
    if len(points) > 1 and np.array_equal(points[0], points[-1]):
        points = points[:-1]
    if len(points) < 2:
        return []
    result = []
    for previous, current in zip(points, np.roll(points, -1, axis=0)):
        dx, dy = current - previous
        if math.isclose(dx, 0, abs_tol=1e-9) and math.isclose(dy, 0, abs_tol=1e-9):
            continue
        theta = math.degrees(math.atan2(dy, dx)) % 360
        result.append(int((theta + 22.5) // 45) % 8)
    return result
