"""
Contour-to-target association.

Implementation status:
    Scaffold only.

Input:
    Contours + target bbox + previous boundary

Output:
    Single target contour (or none)

Owner:
    Module 04 — Boundary Detection
"""

from __future__ import annotations
import cv2
import numpy as np

def associate_contour(contours, target_bbox=None, previous_contour=None):
    """Choose the contour with greatest bbox overlap, then area/continuity."""
    if not contours: return None
    if target_bbox is None and previous_contour is None: return max(contours, key=cv2.contourArea)
    if target_bbox is not None: tx, ty, tw, th = map(float, target_bbox); target = (tx, ty, tx + tw, ty + th)
    else: target = None
    def score(c):
        x, y, w, h = cv2.boundingRect(np.asarray(c, dtype=np.float32).reshape(-1, 1, 2)); overlap = 0.0
        if target:
            ix, iy = max(x, target[0]), max(y, target[1]); ax, ay = min(x + w, target[2]), min(y + h, target[3]); overlap = max(0.0, ax - ix) * max(0.0, ay - iy)
        continuity = 0.0
        if previous_contour is not None: continuity = -float(np.linalg.norm(np.mean(c, axis=0) - np.mean(previous_contour, axis=0)))
        return overlap * 1000.0 + continuity + float(cv2.contourArea(np.asarray(c, dtype=np.float32).reshape(-1, 1, 2)))
    return max(contours, key=score)

select_contour = associate_contour
