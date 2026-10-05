"""Normalize current detections without changing upstream observations."""

from dataclasses import replace

from shared.config import StabilizationConfig
from shared.enums.module_status import ModuleStatus
from shared.schemas.object_frame import ObjectFrame
from shared.schemas.observations import Detection, MotionState


def filter_detections(
    frame: ObjectFrame, config: StabilizationConfig
) -> tuple[list[Detection], int, int]:
    """Suppress exact duplicates only; distinct backend IDs always stay separate.

    No NMS/tracker is recreated here. A lost/predicted box is missing evidence.
    Equal duplicate scores retain the first input occurrence deterministically.
    """
    if frame.status in (ModuleStatus.ERROR, ModuleStatus.INVALID_INPUT):
        return [], len(frame.detections), 0
    chosen = {}
    filtered = duplicates = 0
    for detection in frame.detections:
        if (
            detection.confidence < config.min_detection_confidence
            or detection.track_status == "lost"
            or detection.frames_since_seen > 0
        ):
            filtered += 1
            continue
        key = (
            detection.class_id,
            detection.class_name,
            detection.track_id,
            detection.bbox,
        )
        if key in chosen:
            duplicates += 1
            if chosen[key].confidence >= detection.confidence:
                continue
        chosen[key] = detection
    return (
        [
            replace(
                d,
                is_stable=False,
                duration_frames=1,
                continuity_key=None,
                reference_polygon=None,
                motion=MotionState.UNKNOWN,
                velocity_reference_frame=None,
                identity_ambiguous=False,
                identity_persistent=d.track_id is not None,
                is_context=False,
            )
            for d in chosen.values()
        ],
        filtered,
        duplicates,
    )
