"""Deterministic printed-marker scene for an orientation-aware ground demo."""

import cv2
import numpy as np


def marker_board(size: int = 400) -> np.ndarray:
    image = np.full((size, size), 255, np.uint8)
    dictionary = cv2.aruco.getPredefinedDictionary(cv2.aruco.DICT_4X4_50)
    side = size // 5
    margin = size // 10
    for marker_id, (x, y) in enumerate(
        (
            (margin, margin),
            (size - margin - side, margin),
            (size - margin - side, size - margin - side),
            (margin, size - margin - side),
        )
    ):
        image[y : y + side, x : x + side] = cv2.aruco.generateImageMarker(
            dictionary, marker_id, side
        )
    return cv2.cvtColor(image, cv2.COLOR_GRAY2BGR)
