"""Extract dense contours and restore original-image coordinates."""

from __future__ import annotations

import cv2
import numpy as np


def extract_contours(mask, offset=(0, 0), *, external_only=True):
    if mask is None or np.asarray(mask).size == 0:
        return []
    mode = cv2.RETR_EXTERNAL if external_only else cv2.RETR_LIST
    contours, _ = cv2.findContours(
        (np.asarray(mask) > 0).astype(np.uint8), mode, cv2.CHAIN_APPROX_NONE
    )
    ox, oy = map(float, offset)
    return [
        c.reshape(-1, 2).astype(float) + np.array([ox, oy])
        for c in contours
        if len(c) >= 3
    ]


find_contours = extract_contours
