"""Freeman chain coding.

Direction numbering convention (image-space, y-down):
    0 = East (1, 0)
    1 = South-East (1, 1)
    2 = South (0, 1)
    3 = South-West (-1, 1)
    4 = West (-1, 0)
    5 = North-West (-1, -1)
    6 = North (0, -1)
    7 = North-East (1, -1)

This matches the standard 8-neighbour ordering used with OpenCV contour points in
image coordinates.
"""

from __future__ import annotations

import math
from typing import Iterable, Sequence

import numpy as np


def _as_contour_points(contour: Sequence[Sequence[float]] | np.ndarray) -> np.ndarray:
    """Return a 2D contour array, preserving a repeated closing point when present.

    The final closing step is part of a closed boundary chain, so we keep the
    repeated start point to ensure the contour's last delta is encoded as the
    closing edge rather than silently dropping the final chain segment.
    """
    points = np.asarray(contour, dtype=float)
    if points.size == 0:
        return np.empty((0, 2), dtype=float)
    if points.ndim == 1:
        points = points.reshape(-1, 2)
    if points.ndim != 2 or points.shape[1] != 2:
        raise ValueError(f"Contour must have shape (n, 2), got {points.shape!r}.")
    return points


def _direction_from_delta(dx: float, dy: float) -> int:
    """Map a delta vector to an 8-direction Freeman index using 0..7."""
    if math.isclose(dx, 0.0, abs_tol=1e-9) and math.isclose(dy, 0.0, abs_tol=1e-9):
        raise ValueError("Zero-length step cannot be mapped to a Freeman direction.")

    # Image coordinates use row-down space. The expected 8-neighbour ordering for
    # this project is: 0=E, 1=SE, 2=S, 3=SW, 4=W, 5=NW, 6=N, 7=NE.
    theta = math.degrees(math.atan2(dy, dx))
    theta = (theta + 360.0) % 360.0
    index = int((theta + 22.5) // 45.0) % 8
    return index


def freeman_chain(contour: Sequence[Sequence[float]] | np.ndarray) -> list[int]:
    """Encode a contour as an 8-neighbour Freeman chain code.

    The contour should be ordered around the boundary. If the contour repeats the
    first point at the end as a closing step, that closing point is removed before
    encoding so the chain represents the actual boundary edges without duplicating
    the final segment. Any zero-length step is skipped because it is not a real
    contour transition and would otherwise produce an invalid Freeman direction.
    """
    points = _as_contour_points(contour)
    if points.shape[0] < 2:
        return []

    if np.allclose(points[0], points[-1]):
        points = points[:-1]

    if points.shape[0] < 2:
        return []

    codes: list[int] = []
    for previous, current in zip(points[:-1], points[1:]):
        dx = float(current[0] - previous[0])
        dy = float(current[1] - previous[1])
        if math.isclose(dx, 0.0, abs_tol=1e-9) and math.isclose(dy, 0.0, abs_tol=1e-9):
            continue
        codes.append(_direction_from_delta(dx, dy))
    return codes
