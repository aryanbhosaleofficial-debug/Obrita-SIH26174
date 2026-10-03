"""Functions for boundary and chain-code visualization."""

from __future__ import annotations

from typing import Iterable

import cv2
import matplotlib.pyplot as plt
import numpy as np


def draw_boundary_overlay(original_image: np.ndarray, boundary_points: Iterable[tuple[int, int]], start_point: tuple[int, int], color: tuple[int, int, int] = (0, 0, 255)) -> np.ndarray:
    """Draw the detected boundary and the starting point on the original image."""
    overlay = original_image.copy()
    points = list(boundary_points)

    if not points:
        return overlay

    contour = np.asarray(points, dtype=np.int32).reshape(-1, 1, 2)
    cv2.polylines(overlay, [contour], isClosed=True, color=color, thickness=1, lineType=cv2.LINE_AA)

    cv2.circle(overlay, (int(start_point[0]), int(start_point[1])), 5, (0, 255, 0), -1)
    cv2.putText(
        overlay,
        f"Start: {start_point}",
        (int(start_point[0]) + 10, int(start_point[1]) - 10),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.5,
        (0, 255, 0),
        1,
        cv2.LINE_AA,
    )
    return overlay


def save_image_bytes(image: np.ndarray, fmt: str = ".png") -> bytes:
    """Convert an image to bytes for a download button."""
    success, encoded = cv2.imencode(fmt, image)
    if not success:
        raise ValueError("The image could not be encoded for download.")
    return encoded.tobytes()


def plot_direction_frequencies(frequencies: dict[int, int]) -> plt.Figure:
    """Create a bar chart of direction frequencies."""
    figure, axis = plt.subplots(figsize=(10, 4))
    labels = [str(key) for key in range(8)]
    values = [frequencies.get(key, 0) for key in range(8)]
    axis.bar(labels, values, color="steelblue")
    axis.set_title("Direction Frequency")
    axis.set_xlabel("Direction")
    axis.set_ylabel("Count")
    axis.grid(axis="y", linestyle="--", alpha=0.4)
    figure.tight_layout()
    return figure
