"""Explicit bridge to the existing Module 02 ObjectFrame contract."""

from copy import deepcopy

from perception.contracts import PerceptionFrameResult
from shared.schemas.object_frame import ObjectFrame


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
        detections=deepcopy(result.detections),
        status=result.status,
        source_id=result.source_id,
        session_id=result.session_id,
    )
