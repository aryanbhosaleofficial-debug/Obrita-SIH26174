"""Preprocess an owned ROI without changing source pixels."""

from __future__ import annotations

import cv2
import numpy as np


def preprocess_roi(
    image, *, grayscale=False, blur=0, median=0, normalize=False, resize=None
):
    result = np.asarray(image).copy()
    if result.size == 0:
        return result
    if grayscale and result.ndim == 3:
        result = cv2.cvtColor(result, cv2.COLOR_BGR2GRAY)
    if blur and blur > 1:
        k = int(blur) | 1
        result = cv2.GaussianBlur(result, (k, k), 0)
    if median and median > 1:
        result = cv2.medianBlur(result, int(median) | 1)
    if normalize:
        result = cv2.normalize(result, None, 0, 255, cv2.NORM_MINMAX)
    if resize:
        result = cv2.resize(
            result, tuple(map(int, resize)), interpolation=cv2.INTER_AREA
        )
    return result


preprocess = preprocess_roi
