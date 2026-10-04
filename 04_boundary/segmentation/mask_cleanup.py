"""
Mask cleanup (morphology).

Implementation status:
    Scaffold only.

Input:
    Binary mask

Output:
    Cleaned binary mask

Owner:
    Module 04 — Boundary Detection
"""

from __future__ import annotations
import cv2
import numpy as np

def clean_mask(mask, *, opening=0, closing=0, min_component_area=0):
    result = (np.asarray(mask) > 0).astype(np.uint8) * 255
    for operation, size in ((cv2.MORPH_OPEN, opening), (cv2.MORPH_CLOSE, closing)):
        if size and size > 1:
            k = int(size); result = cv2.morphologyEx(result, operation, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (k, k)))
    if min_component_area > 0 and result.size:
        count, labels, stats, _ = cv2.connectedComponentsWithStats(result, 8); keep = np.zeros_like(result)
        for label in range(1, count):
            if stats[label, cv2.CC_STAT_AREA] >= min_component_area: keep[labels == label] = 255
        result = keep
    return result

cleanup_mask = clean_mask
