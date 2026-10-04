"""Replaceable rack calibration; never infer physical up from the camera."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Protocol

import cv2
import numpy as np

from perception.contracts import Point2D, ReferenceFrameInfo


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
    A dynamic marker implementation should raise ReferenceUnavailableError when lost.
    """

    def update(self, image: np.ndarray) -> ReferenceFrameInfo: ...
    def image_to_reference(
        self, point: Point2D, frame_shape: tuple[int, int]
    ) -> Point2D: ...


class UnavailableReference:
    def update(self, image: np.ndarray) -> ReferenceFrameInfo:
        return ReferenceFrameInfo()

    def image_to_reference(
        self, point: Point2D, frame_shape: tuple[int, int]
    ) -> Point2D:
        raise ReferenceUnavailableError("reference calibration unavailable")


class ManualRackTransformer:
    """Fixed camera/board homography to a unit rack square.

    Corners follow physical rack order: (0,0), (1,0), (1,1), (0,1).
    Their image order can be rotated arbitrarily. This manual calibration cannot
    detect movement of the camera/rack: recalibrate or invalidate it externally.
    """

    def __init__(
        self, corners_normalized: Sequence[Sequence[float]], reference_id: str = "rack"
    ):
        points = validate_corners(corners_normalized)
        self._matrix_normalized = cv2.getPerspectiveTransform(
            points.astype(np.float32),
            np.array([[0, 0], [1, 0], [1, 1], [0, 1]], dtype=np.float32),
        ).astype(np.float64)
        self.reference_id = reference_id
        self._points = points
        self.valid = True

    def image_to_reference(
        self, point: Point2D, frame_shape: tuple[int, int]
    ) -> Point2D:
        if not self.valid:
            raise ReferenceUnavailableError("manual reference invalidated")
        p = normalized_point(point, frame_shape)
        value = self._matrix_normalized @ np.array([p.x, p.y, 1.0])
        if not np.isfinite(value).all() or abs(value[2]) < 1e-9:
            raise ReferenceUnavailableError(
                "point lies on reference projective horizon"
            )
        return Point2D(float(value[0] / value[2]), float(value[1] / value[2]))

    def update(self, image: np.ndarray) -> ReferenceFrameInfo:
        if not self.valid:
            return ReferenceFrameInfo()
        height, width = image.shape[:2]
        matrix = self._matrix_normalized @ np.diag([1 / width, 1 / height, 1])

        # Axes drawn from origin toward the physical +x and +y rack corners.
        def pixel_corner(index: int) -> Point2D:
            return Point2D(
                float(self._points[index, 0] * width),
                float(self._points[index, 1] * height),
            )

        axes = (pixel_corner(0), pixel_corner(1), pixel_corner(3))
        return ReferenceFrameInfo(
            True,
            self.reference_id,
            tuple(tuple(float(v) for v in row) for row in matrix),
            axes,
        )
