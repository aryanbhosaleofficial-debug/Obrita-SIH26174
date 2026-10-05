"""Deterministic local threshold, adaptive threshold and Canny segmentation."""

from __future__ import annotations

import cv2
import numpy as np


def segment(image, method="threshold", **kwargs):
    source = np.asarray(image)
    if source.size == 0:
        return np.zeros(source.shape[:2], dtype=np.uint8)
    gray = (
        cv2.cvtColor(source, cv2.COLOR_BGR2GRAY) if source.ndim == 3 else source.copy()
    )
    method = method.lower()
    if method == "canny":
        return cv2.Canny(gray, kwargs.get("low", 50), kwargs.get("high", 150)).astype(
            np.uint8
        )
    if method in ("adaptive", "adaptive_threshold"):
        block = max(3, int(kwargs.get("block_size", 11)) | 1)
        return cv2.adaptiveThreshold(
            gray,
            255,
            cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
            cv2.THRESH_BINARY,
            block,
            float(kwargs.get("c", 2)),
        )
    threshold = kwargs.get("threshold", 0)
    mode = cv2.THRESH_BINARY_INV if kwargs.get("invert", False) else cv2.THRESH_BINARY
    _, mask = cv2.threshold(
        gray,
        0 if threshold in (None, 0, "otsu") else float(threshold),
        255,
        mode | (cv2.THRESH_OTSU if threshold in (None, 0, "otsu") else 0),
    )
    return mask.astype(np.uint8)


foreground_segment = segment


def candidate_masks(image, method="threshold", **kwargs):
    """Threshold once, then evaluate both polarities; no physical-up assumption."""
    mask = segment(image, method, **kwargs)
    if method == "canny":
        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        filled = np.zeros_like(mask)
        cv2.drawContours(filled, contours, -1, 255, -1)
        return [("edges", filled)]
    inverted = bool(kwargs.get("invert", False))
    return [
        ("dark" if inverted else "bright", mask),
        ("bright" if inverted else "dark", cv2.bitwise_not(mask)),
    ]
