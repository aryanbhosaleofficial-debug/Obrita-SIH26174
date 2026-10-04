"""Input validation for Module 03."""

from __future__ import annotations


def _get(value, *names, default=None):
    if isinstance(value, dict):
        for name in names:
            if name in value:
                return value[name]
    else:
        for name in names:
            if hasattr(value, name):
                return getattr(value, name)
    return default


def validate_inputs(frame=None, frame_id=None, timestamp=None, detections=None):
    """Validate the frame and detection payload used by the optimization pipeline."""
    if frame is None:
        return {"status": "INVALID_INPUT", "reason": "missing_frame"}

    items = list(detections or [])
    if not items:
        return {"status": "NO_PERSON", "reason": "no_detections"}

    person = None
    for detection in items:
        class_name = str(_get(detection, "class_name", "label", default="")).lower()
        if class_name in {"person", "human"}:
            person = detection
            break

    if person is None:
        return {"status": "NO_PERSON", "reason": "missing_person_detection"}

    bbox = _get(person, "bbox", "bbox_xyxy", default=None)
    if bbox is None or len(bbox) < 4:
        return {"status": "INVALID_INPUT", "reason": "invalid_person_bbox"}

    return {
        "status": "OK",
        "frame_id": int(frame_id) if frame_id is not None else None,
        "timestamp": float(timestamp) if timestamp is not None else None,
        "person": person,
        "detections": items,
    }
