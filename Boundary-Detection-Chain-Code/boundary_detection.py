"""OpenCV-based contour detection and object selection for boundary analysis."""

from __future__ import annotations

from typing import Any

import cv2
import numpy as np


def find_external_contours(binary_image: np.ndarray) -> list[np.ndarray]:
    """Find meaningful external contours, ordered from largest to smallest."""
    image = binary_image.copy()
    if image.dtype != np.uint8:
        image = image.astype(np.uint8)

    contours, _ = cv2.findContours(image, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)
    minimum_area = max(16.0, image.shape[0] * image.shape[1] * 0.0001)
    meaningful = [contour for contour in contours if cv2.contourArea(contour) >= minimum_area]
    return sorted(meaningful, key=cv2.contourArea, reverse=True)


def select_contour(contours: list[np.ndarray], object_index: int | None = None) -> tuple[np.ndarray, int]:
    """Return the largest contour by default, or the chosen contour index."""
    if not contours:
        raise ValueError("No object boundary was detected in the image.")

    if object_index is None:
        chosen_index = max(range(len(contours)), key=lambda idx: cv2.contourArea(contours[idx]))
        contour = contours[chosen_index]
    else:
        if object_index < 0 or object_index >= len(contours):
            raise ValueError(f"Invalid object index. Choose a value from 0 to {len(contours) - 1}.")
        chosen_index = object_index
        contour = contours[chosen_index]

    return contour, chosen_index


def detect_boundary(binary_image: np.ndarray, object_index: int | None = None) -> dict[str, Any]:
    """Detect and summarize the selected external boundary."""
    contours = find_external_contours(binary_image)
    if not contours:
        raise ValueError("No boundary was detected. Try a different threshold or upload a clearer image.")

    selected_contour, contour_index = select_contour(contours, object_index)
    boundary_points = selected_contour.reshape(-1, 2)
    area = float(cv2.contourArea(selected_contour))

    return {
        "contours": contours,
        "selected_contour": selected_contour,
        "boundary_points": boundary_points,
        "object_index": contour_index,
        "num_objects": len(contours),
        "area": area,
    }
