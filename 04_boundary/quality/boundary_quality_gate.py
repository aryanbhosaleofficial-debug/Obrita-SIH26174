"""Assess contour evidence quality using explicit heuristic thresholds."""

from __future__ import annotations


def evaluate_quality(
    *,
    contour=None,
    features=None,
    mask=None,
    tracking=None,
    segmentation=None,
    min_confidence=0.35,
):
    reasons = []
    features = features or {}
    tracking = tracking or {}
    if contour is None:
        reasons.append("no boundary contour")
    if mask is not None and getattr(mask, "size", 0) and not mask.any():
        reasons.append("segmentation mask is empty")
    if features.get("area", 0) <= 0:
        reasons.append("invalid contour area")
    shape_score = min(1.0, float(features.get("solidity", 0.0))) if features else 0.0
    track_score = float(tracking.get("tracking_confidence", 0.0)) if tracking else 0.0
    if segmentation is None or segmentation.reasons:
        reasons.extend(
            segmentation.reasons
            if segmentation is not None
            else ["segmentation quality unavailable"]
        )
    segmentation_score = segmentation.score if segmentation is not None else 0.0
    confidence = (
        max(
            0.0,
            min(
                1.0,
                segmentation_score * (0.50 + 0.25 * shape_score + 0.25 * track_score),
            ),
        )
        if contour is not None
        else 0.0
    )
    if confidence < min_confidence:
        reasons.append("confidence below threshold")
    if reasons:
        confidence = 0.0
    status = (
        "VALID" if not reasons else ("NO_BOUNDARY" if contour is None else "UNCERTAIN")
    )
    return {
        "confidence": confidence,
        "status": status,
        "quality_ok": status == "VALID",
        "reasons": reasons,
    }


quality_gate = evaluate_quality
