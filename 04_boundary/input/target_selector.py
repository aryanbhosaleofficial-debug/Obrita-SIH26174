"""Conservative target selection from CURRENT Module 03 observations."""

from shared.schemas.optimization_packet import OptimizationOutputPacket


def select_target(*, object_bbox=None, person_bbox=None, interaction_candidates=None):
    """Legacy explicit bbox entry point; it performs no detection."""
    if object_bbox is None:
        return {"available": False, "reason": "no object bbox"}
    return {
        "available": True,
        "object_bbox": tuple(object_bbox),
        "person_bbox": person_bbox,
        "selection_rule": "explicit upstream target",
    }


def select_optimization_target(
    packet: OptimizationOutputPacket,
    *,
    target_object_track_id=None,
    detection_index=None,
):
    detections = packet.object_frame.detections
    eligible = {i for i, d in enumerate(detections) if d.is_stable and not d.is_context}
    if detection_index is not None:
        if type(detection_index) is not int or detection_index not in eligible:
            return None, "requested detection is absent, unconfirmed or context-only"
        selected = detection_index
        if (
            target_object_track_id is not None
            and detections[selected].track_id != target_object_track_id
        ):
            return None, "requested target selectors disagree"
        return selected, ""
    if target_object_track_id is not None:
        matches = [
            i for i in eligible if detections[i].track_id == target_object_track_id
        ]
        return (
            (matches[0], "")
            if len(matches) == 1
            else (None, "requested object is not currently confirmed")
        )
    associated = {
        candidate.detection_index
        for candidate in packet.interactions
        if candidate.observed
        and not candidate.ambiguous
        and candidate.detection_index in eligible
    }
    if len(associated) == 1:
        return next(iter(associated)), ""
    if len(eligible) == 1:
        return next(iter(eligible)), ""
    return None, "no unique current confirmed target; provide a target selector"
