"""Image preprocessing utilities for the boundary-detection project."""

from __future__ import annotations

from pathlib import Path
from typing import Optional, Union

import cv2
import numpy as np


ImageLike = Union[np.ndarray, bytes]


def load_image(image_path: Optional[Union[str, Path]] = None, uploaded_file: Optional[object] = None) -> np.ndarray:
    """Load an image from a file path or a Streamlit uploaded object."""
    if uploaded_file is not None:
        file_bytes = uploaded_file.read()
        if not file_bytes:
            raise ValueError("The uploaded file is empty.")
        array = np.frombuffer(file_bytes, dtype=np.uint8)
        image = cv2.imdecode(array, cv2.IMREAD_COLOR)
    elif image_path is not None:
        image = cv2.imread(str(image_path), cv2.IMREAD_COLOR)
    else:
        raise ValueError("No image path or uploaded file was provided.")

    if image is None or image.size == 0:
        raise ValueError("The image could not be loaded or is invalid.")

    return image


def to_grayscale(image: np.ndarray) -> np.ndarray:
    """Convert a BGR color image to grayscale using OpenCV."""
    if image.ndim != 3:
        raise ValueError("The input image must be a color image.")
    return cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)


def threshold_image(gray_image: np.ndarray, threshold_value: int = 127) -> np.ndarray:
    """Convert the grayscale image to a binary image where the object is the foreground (255)."""
    if not isinstance(threshold_value, int):
        raise ValueError("Threshold must be a valid integer value.")

    if threshold_value < 0 or threshold_value > 255:
        raise ValueError("Threshold must be in the range 0 to 255.")

    # In this project, we assume the object is darker than the background by default.
    # This is the standard setup for many academic examples such as black shapes on white paper.
    binary = np.zeros_like(gray_image, dtype=np.uint8)
    binary[gray_image < threshold_value] = 255
    return binary


def preprocess_image(
    image: np.ndarray,
    threshold_value: int | None = None,
    apply_blur: bool = True,
    blur_kernel: tuple[int, int] = (5, 5),
) -> dict[str, np.ndarray]:
    """Return grayscale, denoised, and morphologically cleaned foreground images."""
    gray = to_grayscale(image)
    processed_gray = gray

    if apply_blur:
        kernel = tuple(value if value % 2 else value + 1 for value in blur_kernel)
        processed_gray = cv2.GaussianBlur(gray, kernel, 0)

    if threshold_value is None:
        otsu_value, _ = cv2.threshold(
            processed_gray, 0, 255, cv2.THRESH_BINARY | cv2.THRESH_OTSU
        )
        border = np.concatenate(
            (processed_gray[0, :], processed_gray[-1, :], processed_gray[:, 0], processed_gray[:, -1])
        )
        invert = float(np.median(border)) > otsu_value
        mode = cv2.THRESH_BINARY_INV if invert else cv2.THRESH_BINARY
        _, binary = cv2.threshold(
            processed_gray, 0, 255, mode | cv2.THRESH_OTSU
        )
    else:
        binary = threshold_image(processed_gray, threshold_value)

    if min(binary.shape) >= 3:
        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))
        binary = cv2.morphologyEx(binary, cv2.MORPH_OPEN, kernel)
        binary = cv2.morphologyEx(binary, cv2.MORPH_CLOSE, kernel)

    return {
        "original": image,
        "grayscale": gray,
        "blurred": processed_gray,
        "binary": binary,
    }


def invert_binary(binary: np.ndarray) -> np.ndarray:
    """Invert a binary image so that the object pixels are white."""
    return cv2.bitwise_not(binary)
