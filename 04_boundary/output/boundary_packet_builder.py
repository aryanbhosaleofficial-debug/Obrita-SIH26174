"""Always publish the authoritative shared BoundaryOutputPacket."""

from shared.enums.boundary_state import BoundaryState
from shared.enums.module_status import ModuleStatus
from shared.schemas.boundary_packet import BoundaryOutputPacket


def build_packet(
    *,
    frame_id: int,
    timestamp: float,
    contour=None,
    chain_code=None,
    features=None,
    tracking=None,
    interaction=None,
    quality=None,
    target_track_id=None,
    target_object_track_id=None,
    differential_chain_code=None,
    chain_histogram=None,
    boundary_state=None,
    state_confirmed: bool = False,
    confirmed_frames: int = 0,
    status: ModuleStatus | None = None,
) -> BoundaryOutputPacket:
    features, interaction, quality = features or {}, interaction or {}, quality or {}
    quality_ok = bool(quality.get("quality_ok", False))
    reasons = list(quality.get("reasons", []))
    if not quality_ok and not reasons:
        reasons = ["boundary quality check failed"]
    return BoundaryOutputPacket(
        frame_id=frame_id,
        timestamp_s=timestamp,
        target_track_id=target_track_id,
        target_object_track_id=target_object_track_id,
        boundary_state=boundary_state
        if quality_ok and boundary_state is not None
        else BoundaryState.UNKNOWN,
        state_confirmed=bool(quality_ok and state_confirmed),
        confirmed_frames=confirmed_frames if quality_ok and state_confirmed else 0,
        contour_px=[] if contour is None else [tuple(map(float, p)) for p in contour],
        chain_code=list(chain_code or []),
        differential_chain_code=list(differential_chain_code or []),
        chain_histogram=list(chain_histogram or []),
        area_px=features.get("area"),
        perimeter_px=features.get("perimeter"),
        centroid_px=tuple(features["centroid"])
        if features.get("centroid") is not None
        else None,
        hand_contact=quality_ok and bool(interaction.get("near_boundary", False)),
        contact_confidence=float(interaction.get("contact_proxy", 0.0))
        if quality_ok
        else 0.0,
        confidence=float(quality.get("confidence", 0.0)) if quality_ok else 0.0,
        quality_ok=quality_ok,
        quality_reasons=[] if quality_ok else reasons,
        status=status
        if status is not None
        else ModuleStatus.OK
        if quality_ok
        else ModuleStatus.DEGRADED,
    )


create_boundary_packet = build_packet
