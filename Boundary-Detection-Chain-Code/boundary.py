"""Compatibility exports for the shared contour-detection implementation."""

from __future__ import annotations

import numpy as np

from boundary_detection import detect_boundary, find_external_contours, select_contour


def get_boundary_points(contour: np.ndarray) -> np.ndarray:
    """Convert a contour into its ordered boundary-pixel coordinates."""
    if contour.size == 0:
        raise ValueError("The contour is empty and cannot be traced.")
    return contour.reshape(-1, 2)
