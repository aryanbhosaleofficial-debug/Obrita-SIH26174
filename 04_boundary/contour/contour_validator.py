"""Measure and validate contours before selecting the largest eligible component."""

from __future__ import annotations

import cv2
import numpy as np


def contour_metrics(contour):
    points = (
        np.asarray(contour, dtype=np.float32).reshape(-1, 1, 2)
        if contour is not None
        else np.empty((0, 1, 2), np.float32)
    )
    if len(points) < 3:
        return {
            "area": 0.0,
            "perimeter": 0.0,
            "bbox": (0, 0, 0, 0),
            "centroid": None,
            "solidity": 0.0,
            "valid": False,
        }
    area = float(cv2.contourArea(points))
    perimeter = float(cv2.arcLength(points, True))
    bbox = tuple(map(int, cv2.boundingRect(points)))
    moments = cv2.moments(points)
    centroid = (
        (moments["m10"] / moments["m00"], moments["m01"] / moments["m00"])
        if moments["m00"]
        else None
    )
    hull_area = float(cv2.contourArea(cv2.convexHull(points)))
    return {
        "area": area,
        "perimeter": perimeter,
        "bbox": bbox,
        "centroid": centroid,
        "solidity": area / hull_area if hull_area else 0.0,
        "valid": True,
    }


def validate_contour(
    contour,
    *,
    min_area=1.0,
    max_area=None,
    min_perimeter=0.0,
    min_width=0.0,
    min_height=0.0,
    min_solidity=0.0,
):
    m = contour_metrics(contour)
    if not m["valid"]:
        return False, m, "contour has fewer than three points"
    _, _, w, h = m["bbox"]
    if m["area"] < min_area:
        return False, m, "contour area below minimum"
    if max_area is not None and m["area"] > max_area:
        return False, m, "contour area above maximum"
    if m["perimeter"] < min_perimeter:
        return False, m, "contour perimeter below minimum"
    if w < min_width or h < min_height:
        return False, m, "contour bounding box too small"
    if m["solidity"] < min_solidity:
        return False, m, "contour solidity below minimum"
    return True, m, ""


def select_best_contour(contours, **limits):
    candidates = [
        (c, contour_metrics(c)) for c in contours if validate_contour(c, **limits)[0]
    ]
    if not candidates:
        return None, {}, "no valid contour"
    return (
        max(candidates, key=lambda item: item[1]["area"])[0],
        max(candidates, key=lambda item: item[1]["area"])[1],
        "",
    )


def border_metrics(contour, roi_shape, *, margin_px=1):
    """Contour is in ROI-local pixels. Single-side clipping is not rejection."""
    points = np.asarray(contour).reshape(-1, 2)
    height, width = roi_shape[:2]
    if not len(points):
        return {"sides_touched": 0, "point_fraction": 0.0, "bbox_matches_roi": False}
    sides = np.column_stack(
        (
            points[:, 0] <= margin_px,
            points[:, 0] >= width - 1 - margin_px,
            points[:, 1] <= margin_px,
            points[:, 1] >= height - 1 - margin_px,
        )
    )
    low, high = points.min(axis=0), points.max(axis=0)
    return {
        "sides_touched": int(sides.any(axis=0).sum()),
        "point_fraction": float(sides.any(axis=1).mean()),
        "bbox_matches_roi": bool(
            low[0] <= margin_px
            and low[1] <= margin_px
            and high[0] >= width - 1 - margin_px
            and high[1] >= height - 1 - margin_px
        ),
    }
