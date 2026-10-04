"""Shared coordinate contracts and pure geometry; no model or calibration owner."""

import math
from collections.abc import Sequence
from typing import Protocol

import numpy as np

from shared.schemas.observations import Point2D, ReferenceFrameInfo


class ReferenceUnavailableError(ValueError):
    pass


def normalized_point(point: Point2D, frame_shape: tuple[int, int]) -> Point2D:
    height, width = frame_shape
    if height <= 0 or width <= 0:
        raise ValueError("frame dimensions must be positive")
    return Point2D(point.x / width, point.y / height)


def validate_corners(corners: Sequence[Sequence[float]]) -> np.ndarray:
    """Require a finite convex quadrilateral in normalized-image units."""
    try:
        points = np.asarray(corners, dtype=np.float64)
    except (ValueError, TypeError) as exc:
        raise ValueError("rack corners must be four numeric pairs") from exc
    if (
        points.shape != (4, 2)
        or not np.isfinite(points).all()
        or np.any((points < 0) | (points > 1))
    ):
        raise ValueError("rack corners must be four finite normalized pairs in [0, 1]")
    edges = np.roll(points, -1, axis=0) - points
    cross = edges[:, 0] * np.roll(edges[:, 1], -1) - edges[:, 1] * np.roll(
        edges[:, 0], -1
    )
    if not (np.all(cross > 1e-6) or np.all(cross < -1e-6)):
        raise ValueError(
            "rack corners must form a nondegenerate convex ordered quadrilateral"
        )
    return points


class CoordinateTransformer(Protocol):
    """update validates calibration for this frame; transforms use source pixels.

    Implementations must supply a stable reference_id that changes on recalibration.
    update returns valid=False when markers are lost; transforming then raises
    ReferenceUnavailableError. A stable marker layout retains its reference_id
    across camera/board rotation; changing physical axes requires a new ID.
    """

    def update(self, image: np.ndarray) -> ReferenceFrameInfo: ...
    def image_to_reference(
        self, point: Point2D, frame_shape: tuple[int, int]
    ) -> Point2D: ...


def isotropic_point(point: Point2D, frame_shape: tuple[int, int]) -> Point2D:
    height, width = frame_shape
    if height <= 0 or width <= 0:
        raise ValueError("frame dimensions must be positive")
    scale = math.hypot(width, height)
    return Point2D(point.x / scale, point.y / scale)
