"""
Boundary quality gate.

Implementation status:
    Scaffold only.

Input:
    All Module 04 intermediate results

Output:
    quality_ok flag + quality reasons

Owner:
    Module 04 — Boundary Detection
"""

from __future__ import annotations

def evaluate_quality(*, contour=None, features=None, mask=None, tracking=None, min_confidence=0.35):
    reasons = []; features = features or {}; tracking = tracking or {}
    if contour is None: reasons.append("no boundary contour")
    if mask is not None and getattr(mask, "size", 0) and not mask.any(): reasons.append("segmentation mask is empty")
    if features.get("area", 0) <= 0: reasons.append("invalid contour area")
    shape_score = min(1.0, float(features.get("solidity", 0.0))) if features else 0.0
    track_score = float(tracking.get("tracking_confidence", 0.0)) if tracking else 0.0
    confidence = max(0.0, min(1.0, 0.65 * shape_score + 0.35 * track_score)) if contour is not None else 0.0
    if confidence < min_confidence: reasons.append("confidence below threshold")
    status = "VALID" if not reasons else ("NO_BOUNDARY" if contour is None else "UNCERTAIN")
    return {"confidence": confidence, "status": status, "quality_ok": status == "VALID", "reasons": reasons}

quality_gate = evaluate_quality
