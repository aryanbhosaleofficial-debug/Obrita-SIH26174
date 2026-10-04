"""
Boundary ROI generation.

Implementation status:
    Scaffold only.

Input:
    Target bbox (+ hand landmarks)

Output:
    ROI crop and offset in original-frame pixels

Owner:
    Module 04 — Boundary Detection
"""

# TODO: Pad ROI using configs/boundary.yaml.
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np


@dataclass(frozen=True)
class ROIResult:
    image: np.ndarray
    x: int
    y: int
    width: int
    height: int
    valid: bool
    reason: str = ""

    @property
    def offset(self) -> tuple[int, int]:
        return self.x, self.y

    def to_original(self, points: Any) -> np.ndarray:
        result = np.asarray(points, dtype=float).copy()
        if result.size:
            result.reshape(-1, 2)[:, 0] += self.x
            result.reshape(-1, 2)[:, 1] += self.y
        return result


def extract_roi(frame: Any, roi: dict[str, Any] | tuple[float, float, float, float], *, normalized: bool = False, padding: int = 0) -> ROIResult:
    image = np.asarray(frame) if frame is not None else np.empty((0, 0), dtype=np.uint8)
    if image.ndim < 2 or image.size == 0:
        return ROIResult(np.empty((0, 0), dtype=image.dtype), 0, 0, 0, 0, False, "frame is empty")
    values = [roi.get(k, 0) for k in ("x", "y", "width", "height")] if isinstance(roi, dict) else list(roi)
    if len(values) != 4: return ROIResult(np.empty((0, 0), dtype=image.dtype), 0, 0, 0, 0, False, "ROI must have four values")
    try:
        x, y, w, h = map(float, values); height, width = image.shape[:2]
        if normalized: x, y, w, h = x * width, y * height, w * width, h * height
        x1, y1, x2, y2 = int(np.floor(x - padding)), int(np.floor(y - padding)), int(np.ceil(x + w + padding)), int(np.ceil(y + h + padding))
    except (TypeError, ValueError): return ROIResult(np.empty((0, 0), dtype=image.dtype), 0, 0, 0, 0, False, "ROI values are invalid")
    x1, y1, x2, y2 = max(0, x1), max(0, y1), min(width, x2), min(height, y2)
    if x2 <= x1 or y2 <= y1: return ROIResult(np.empty((0, 0), dtype=image.dtype), x1, y1, 0, 0, False, "ROI does not intersect frame")
    return ROIResult(image[y1:y2, x1:x2].copy(), x1, y1, x2 - x1, y2 - y1, True)


crop_roi = extract_roi
