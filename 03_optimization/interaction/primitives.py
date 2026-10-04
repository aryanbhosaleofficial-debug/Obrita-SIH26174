"""Generic candidate generation; confirmation happens in the stabilizer."""

from shared.schemas.observations import (
    CoordinateFrame,
    Detection,
    HandObjectAssociation,
    HandObservation,
    InteractionPrimitive,
    InteractionType,
    MotionState,
)
from shared.utils.observation import combine_confidence


def interaction_candidates(
    detections: list[Detection],
    hands: list[HandObservation],
    associations: list[HandObjectAssociation],
) -> list[InteractionPrimitive]:
    candidates = []
    for association in associations:
        if association.is_context:
            continue
        d, h = detections[association.detection_index], hands[association.hand_index]
        labels = []
        if association.near:
            labels.append(InteractionType.NEAR)
        if association.contact_candidate:
            labels.append(InteractionType.CONTACT)
        if association.landmarks_inside or association.hand_box_iou > 0:
            labels.append(InteractionType.OVERLAP)
        if association.leaving_transition:
            labels.append(InteractionType.LEAVING)
        for label in labels:
            candidates.append(
                InteractionPrimitive(
                    label,
                    h.hand_id,
                    str(d.track_id) if d.track_id is not None else None,
                    d.class_name,
                    combine_confidence(d.confidence, h.confidence)
                    if label == InteractionType.LEAVING
                    else association.confidence,
                    detection_index=association.detection_index,
                    hand_index=association.hand_index,
                    coordinate_frame=association.coordinate_frame,
                    identity_reliable=d.track_id is not None and h.identity_persistent,
                    hand_continuity_key=h.continuity_key,
                    object_continuity_key=d.continuity_key,
                    ambiguous=association.ambiguous,
                )
            )
    for di, detection in enumerate(detections):
        if detection.motion == MotionState.MOVING:
            candidates.append(
                InteractionPrimitive(
                    InteractionType.MOTION,
                    None,
                    str(detection.track_id) if detection.track_id is not None else None,
                    detection.class_name,
                    combine_confidence(detector=detection.confidence),
                    detection_index=di,
                    coordinate_frame=CoordinateFrame.RACK_RELATIVE,
                    identity_reliable=detection.track_id is not None,
                    object_continuity_key=detection.continuity_key,
                )
            )
    return candidates
