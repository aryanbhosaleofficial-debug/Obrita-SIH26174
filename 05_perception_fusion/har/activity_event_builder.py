"""Publish the shared contract; UNKNOWN results are never emitted events."""
from shared.schemas.activity_event import ActivityEvent
from shared.enums.module_status import ModuleStatus


def build(packet, detection, candidate, confirmed, emitted, start, event_id, conflicts, evidence):
    label, confidence, rule, support = candidate
    start = start or (packet.frame_id, packet.timestamp_s)
    return ActivityEvent(
        event_id=event_id or f"unknown-{packet.frame_id}",
        activity_label=label if confirmed else "unknown",
        frame_id=packet.frame_id, timestamp_s=packet.timestamp_s,
        start_frame_id=start[0], end_frame_id=packet.frame_id,
        start_timestamp_s=start[1], end_timestamp_s=packet.timestamp_s,
        target_track_id=packet.target_track_id,
        target_object_track_id=detection.track_id if detection else None,
        target_object_class=detection.class_name if detection else None,
        confidence=confidence if confirmed else 0.0,
        evidence_summary=support, conflicts=conflicts,
        status=ModuleStatus.OK if confirmed else ModuleStatus.NO_DETECTION,
        metadata={"source_id": packet.source_id, "session_id": packet.session_id,
                  "confirmed": confirmed, "emitted": emitted, "candidate_label": label,
                  "candidate_confidence": confidence, "rule": rule,
                  "evidence": {s: {"value": item[0], "confidence": item[1]} for s, item in evidence.items()}},
    )
