"""Pair the existing prepared image with its canonical object metadata."""

from shared.schemas.frame_packet import FramePacket
from shared.schemas.object_frame import ObjectFrame
from shared.schemas.prepared_frame import PreparedFrame


def validate_pair(prepared: PreparedFrame, objects: ObjectFrame) -> FramePacket:
    """Source lookup/ownership stays with the caller; no frame queue lives here."""
    if not isinstance(prepared, PreparedFrame) or not isinstance(objects, ObjectFrame):
        raise TypeError("OptimizationPipeline requires PreparedFrame and ObjectFrame")
    source = prepared.source
    if source is None:
        raise ValueError("PreparedFrame must retain source")
    if (
        objects.frame_id,
        objects.timestamp_s,
        objects.source_id,
        objects.session_id,
        objects.image_width,
        objects.image_height,
    ) != (
        source.frame_id,
        source.timestamp_s,
        source.source_id,
        source.session_id,
        source.width,
        source.height,
    ):
        raise ValueError("ObjectFrame metadata does not match PreparedFrame source")
    return source
