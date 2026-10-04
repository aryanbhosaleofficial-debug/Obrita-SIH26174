"""Explicit bridge to the existing Module 02 ObjectFrame contract."""

from perception.contracts import PerceptionFrameResult
from shared.schemas.object_frame import DetectedObject, ObjectFrame


def to_object_frame(result: PerceptionFrameResult) -> ObjectFrame:
    """Copy object observations; no reinference and no fabricated rack anchors.

    Existing Module 02 consumers can use this bridge. Hand/interaction consumers
    should accept PerceptionFrameResult directly. No procedure interpretation.
    """
    return ObjectFrame(
        result.frame_id,
        result.timestamp_s,
        result.image_width,
        result.image_height,
        detections=[
            DetectedObject(
                d.class_name,
                d.class_id,
                d.confidence,
                (d.bbox.x1, d.bbox.y1, d.bbox.x2, d.bbox.y2),
                track_id=d.track_id,
                track_status="confirmed"
                if d.is_stable and d.track_id is not None
                else "tentative",
                track_age_frames=d.duration_frames if d.track_id is not None else 0,
                is_stable=d.is_stable,
            )
            for d in result.detections
        ],
        status=result.status,
    )
