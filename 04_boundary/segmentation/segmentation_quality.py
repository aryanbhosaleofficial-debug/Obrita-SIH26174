"""Conservative, explainable ROI mask assessment; demo thresholds need tuning."""

from dataclasses import dataclass

import cv2
import numpy as np

from ..contour.contour_extractor import extract_contours
from ..contour.contour_validator import border_metrics, validate_contour


@dataclass
class SegmentationAssessment:
    contour: np.ndarray | None
    score: float
    reasons: list[str]
    metrics: dict[str, float]


def grayscale(image):
    return cv2.cvtColor(image, cv2.COLOR_BGR2GRAY) if image.ndim == 3 else image


def assess_mask(mask, gray, config) -> SegmentationAssessment:
    """Require occupancy, dominance, filled-contour consistency and contrast."""
    foreground = mask > 0
    count = int(foreground.sum())
    fraction = count / mask.size
    variance = float(np.var(gray, dtype=np.float64))
    metrics = {"occupancy": fraction, "stddev": variance**0.5}
    reasons = []
    if metrics["stddev"] < config.min_roi_stddev:
        reasons.append("low-information ROI")
    if not config.min_foreground_fraction <= fraction <= config.max_foreground_fraction:
        reasons.append("foreground occupancy outside configured range")
    if reasons:
        return SegmentationAssessment(None, 0.0, reasons, metrics)
    # Between-class / total variance measures binary foreground/background
    # separation. Random intensity noise does not have clean object contrast.
    separation = (
        fraction
        * (1 - fraction)
        * (float(gray[foreground].mean()) - float(gray[~foreground].mean())) ** 2
        / variance
    )
    metrics["separability"] = min(1.0, separation)
    if separation < config.min_separability:
        return SegmentationAssessment(
            None, 0.0, ["weak foreground/background separation"], metrics
        )
    _, labels, stats, _ = cv2.connectedComponentsWithStats(mask, connectivity=8)
    label = 1 + int(np.argmax(stats[1:, cv2.CC_STAT_AREA]))
    if stats[label, cv2.CC_STAT_AREA] / count < config.min_component_dominance:
        return SegmentationAssessment(None, 0.0, ["fragmented foreground"], metrics)
    component = (labels == label).astype(np.uint8) * 255
    candidates = []
    for contour in extract_contours(component):
        valid, geometry, reason = validate_contour(
            contour,
            min_area=config.min_area,
            max_area=config.max_area,
            min_perimeter=config.min_perimeter,
        )
        if not valid:
            reasons.append(reason)
            continue
        border = border_metrics(contour, mask.shape, margin_px=config.border_margin_px)
        if border["bbox_matches_roi"] or (
            border["sides_touched"] > config.max_border_sides
            and border["point_fraction"] >= config.max_border_point_fraction
        ):
            reasons.append("ROI-border contour rejected")
            continue
        # Filled contour versus actual foreground catches hollow background
        # contours, fragmented noise and internal holes. All operations vectorized.
        filled = np.zeros_like(mask)
        cv2.drawContours(
            filled, [contour.astype(np.int32).reshape(-1, 1, 2)], -1, 255, -1
        )
        region = filled > 0
        inside = int(np.count_nonzero(foreground & region))
        dominance = inside / count
        density = inside / int(region.sum())
        if geometry["area"] / mask.size > config.max_foreground_fraction:
            reasons.append("contour fills almost entire ROI")
            continue
        if (
            dominance < config.min_component_dominance
            or density < config.min_contour_fill_fraction
        ):
            reasons.append("fragmented or inconsistent foreground")
            continue
        score = min(separation, dominance, density, 1 - border["point_fraction"])
        evidence = {
            **metrics,
            "component_dominance": dominance,
            "contour_fill_fraction": density,
            "border_fraction": border["point_fraction"],
            "border_sides": border["sides_touched"],
        }
        candidates.append(SegmentationAssessment(contour, float(score), [], evidence))
    if not candidates:
        return SegmentationAssessment(
            None, 0.0, sorted(set(reasons)) or ["no valid contour"], metrics
        )
    # Quality first, area only as a deterministic tie-breaker among valid masks.
    return max(
        candidates,
        key=lambda c: (c.score, cv2.contourArea(c.contour.astype(np.float32))),
    )
