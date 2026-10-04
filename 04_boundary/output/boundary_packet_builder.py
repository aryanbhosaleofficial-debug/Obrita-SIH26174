"""
BoundaryOutputPacket builder.

Implementation status:
    Scaffold only.

Input:
    Boundary features, state, cross-check and quality results

Output:
    BoundaryOutputPacket (shared/schemas/boundary_packet.py)

Owner:
    Module 04 — Boundary Detection
"""

from __future__ import annotations

from typing import Any

try:
    from shared.schemas.boundary_packet import BoundaryOutputPacket
    from shared.enums.boundary_state import BoundaryState
    from shared.enums.module_status import ModuleStatus
except ImportError:
    BoundaryOutputPacket = None


def build_packet(*, frame_id: int, timestamp: float, contour=None, chain_code=None,
                 features=None, tracking=None, interaction=None, quality=None,
                 target_track_id=None, differential_chain_code=None, chain_histogram=None,
                 boundary_state=None, **kwargs: Any):
    """Build the shared packet when available, otherwise return a JSON-safe dict."""
    features = features or {}; tracking = tracking or {}; interaction = interaction or {}; quality = quality or {}
    quality_ok = bool(quality.get("quality_ok", quality.get("status") == "VALID"))
    reasons = list(quality.get("reasons", quality.get("quality_reasons", [])))
    if not quality_ok and not reasons: reasons = ["boundary quality check failed"]
    if BoundaryOutputPacket is None: return {"module": "boundary_detection", "frame_id": frame_id, "timestamp": timestamp, "status": quality.get("status", "NO_BOUNDARY"), "boundary": {"bbox": features.get("bbox"), "centroid": features.get("centroid"), "area": features.get("area", 0.0), "perimeter": features.get("perimeter", 0.0), "chain_code": chain_code or [], "confidence": quality.get("confidence", 0.0)}, "features": features, "tracking": tracking, "hand_boundary_interaction": interaction, "quality": quality}
    status = ModuleStatus.OK if quality_ok else ModuleStatus.DEGRADED
    state = boundary_state if boundary_state is not None else BoundaryState.UNKNOWN
    contour_points = [] if contour is None else contour
    return BoundaryOutputPacket(frame_id=int(frame_id), timestamp_s=float(timestamp), target_track_id=target_track_id,
        contour_px=[tuple(map(float, p)) for p in contour_points], chain_code=list(chain_code or []),
        differential_chain_code=list(differential_chain_code or []), chain_histogram=list(chain_histogram or []),
        area_px=features.get("area"), perimeter_px=features.get("perimeter"), centroid_px=tuple(features["centroid"]) if features.get("centroid") else None,
        hand_contact=bool(interaction.get("near_boundary", False)), contact_confidence=float(interaction.get("contact_proxy", 0.0)),
        confidence=float(quality.get("confidence", 0.0)), quality_ok=quality_ok, quality_reasons=reasons, status=status, boundary_state=state)

create_boundary_packet = build_packet
