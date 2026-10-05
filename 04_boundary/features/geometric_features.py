"""Pixel geometry only; no image-axis angle is published as rack orientation."""

import math

from ..contour.contour_validator import contour_metrics


def extract_features(contour, chain_code=None):
    metrics = contour_metrics(contour)
    x, y, width, height = metrics["bbox"]
    area, perimeter = metrics["area"], metrics["perimeter"]
    return {
        "area": area,
        "perimeter": perimeter,
        "width": width,
        "height": height,
        "aspect_ratio": width / height if height else 0.0,
        "centroid": metrics["centroid"],
        "bbox": [x, y, width, height],
        "solidity": metrics["solidity"],
        "compactness": 4 * math.pi * area / perimeter**2 if perimeter else 0.0,
        "chain_code_length": len(chain_code or []),
    }


geometric_features = extract_features
