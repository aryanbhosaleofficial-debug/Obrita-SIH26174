"""Module 04 receiving boundary. Validates real packets; performs no segmentation."""

import math

from shared.enums.module_status import ModuleStatus
from shared.schemas.frame_packet import FramePacket
from shared.schemas.observations import CoordinateFrame
from shared.schemas.optimization_packet import OptimizationOutputPacket


class BoundaryInputError(ValueError):
    pass


def validate_boundary_input(
    packet: OptimizationOutputPacket, frame: FramePacket
) -> None:
    """Reject mismatched frames/units/identity before a boundary backend uses them."""
    if not isinstance(packet, OptimizationOutputPacket) or not isinstance(
        frame, FramePacket
    ):
        raise BoundaryInputError("expected OptimizationOutputPacket and FramePacket")
    if packet.status in (ModuleStatus.ERROR, ModuleStatus.INVALID_INPUT):
        raise BoundaryInputError("optimization did not produce usable output")
    if (packet.frame_id, packet.timestamp_s, packet.source_id, packet.session_id) != (
        frame.frame_id,
        frame.timestamp_s,
        frame.source_id,
        frame.session_id,
    ):
        raise BoundaryInputError("source/session/frame metadata mismatch")
    objects, spatial, obs = packet.object_frame, packet.spatial, packet.observations
    if objects is None or spatial is None or obs is None:
        raise BoundaryInputError("missing required object/spatial/observation packets")
    for part in (objects, spatial, obs):
        if (part.frame_id, part.timestamp_s) != (frame.frame_id, frame.timestamp_s):
            raise BoundaryInputError("cross-frame packet mixture")
    for part in (objects, obs):
        if (part.source_id, part.session_id) != (frame.source_id, frame.session_id):
            raise BoundaryInputError("nested source/session metadata mismatch")
    if (objects.image_width, objects.image_height) != (frame.width, frame.height):
        raise BoundaryInputError("source dimensions mismatch")
    if (obs.image_width, obs.image_height) != (frame.width, frame.height):
        raise BoundaryInputError("observation dimensions mismatch")
    _validate_temporal_evidence(packet)
    if (
        objects.detections != obs.detections
        or spatial.hands != obs.hands
        or packet.interactions != obs.interactions
    ):
        raise BoundaryInputError("inconsistent observation payloads")
    if (
        spatial.reference_frame != obs.reference_frame
        or obs.reference_frame.valid != obs.coordinate_frame_valid
    ):
        raise BoundaryInputError("inconsistent reference metadata")
    for association in obs.associations:
        if association.coordinate_frame != obs.association_coordinate_frame:
            raise BoundaryInputError("mixed coordinate frames")
        if (
            association.coordinate_frame == CoordinateFrame.RACK_RELATIVE
            and not obs.coordinate_frame_valid
        ):
            raise BoundaryInputError("rack geometry without calibration")
        if not 0 <= association.detection_index < len(
            objects.detections
        ) or not 0 <= association.hand_index < len(spatial.hands):
            raise BoundaryInputError("association refers to absent observations")
        units = {
            CoordinateFrame.RACK_RELATIVE: "rack_units",
            CoordinateFrame.IMAGE_DIAGONAL: "image_diagonal_units",
        }
        if association.distance_units != units.get(association.coordinate_frame):
            raise BoundaryInputError("unsupported or mismatched distance units")
        if (association.object_key, association.hand_key) != (
            objects.detections[association.detection_index].continuity_key,
            spatial.hands[association.hand_index].continuity_key,
        ):
            raise BoundaryInputError("association continuity mismatch")
    for interaction in packet.interactions:
        if not 0 <= interaction.detection_index < len(objects.detections):
            raise BoundaryInputError("interaction refers to absent object")
        detection = objects.detections[interaction.detection_index]
        expected_id = (
            str(detection.track_id) if detection.track_id is not None else None
        )
        if (
            interaction.object_id != expected_id
            or interaction.object_continuity_key != detection.continuity_key
        ):
            raise BoundaryInputError("interaction identity mismatch")
        if interaction.coordinate_frame != obs.association_coordinate_frame:
            raise BoundaryInputError("mixed coordinate frames")
        if interaction.hand_index is not None:
            if not 0 <= interaction.hand_index < len(spatial.hands):
                raise BoundaryInputError("interaction refers to absent hand")
            hand = spatial.hands[interaction.hand_index]
            if (
                interaction.hand_continuity_key != hand.continuity_key
                or interaction.hand_id != hand.hand_id
            ):
                raise BoundaryInputError("interaction hand identity mismatch")


def _validate_temporal_evidence(packet: OptimizationOutputPacket) -> None:
    """Held evidence is allowed only in the explicit temporal payload."""
    from shared.schemas.optimization_packet import TemporalDetection, TemporalFrame

    window = packet.temporal_window
    if not window or not all(isinstance(row, TemporalFrame) for row in window):
        raise BoundaryInputError("missing or invalid temporal window")
    if (window[-1].frame_id, window[-1].timestamp_s) != (
        packet.frame_id,
        packet.timestamp_s,
    ):
        raise BoundaryInputError("temporal window does not end at current frame")
    previous = None
    width, height = packet.object_frame.image_width, packet.object_frame.image_height
    for row in window:
        if previous is not None and (
            row.frame_id <= previous.frame_id or row.timestamp_s <= previous.timestamp_s
        ):
            raise BoundaryInputError("unordered temporal window")
        previous = row
        keys = set()
        for evidence in row.detections:
            if not isinstance(evidence, TemporalDetection):
                raise BoundaryInputError("invalid temporal detection type")
            if evidence.continuity_key in keys:
                raise BoundaryInputError("duplicate temporal identity")
            keys.add(evidence.continuity_key)
            if (
                not math.isfinite(evidence.confidence)
                or not 0 <= evidence.confidence <= 1
                or not math.isfinite(evidence.raw_confidence)
                or not 0 <= evidence.raw_confidence <= 1
            ):
                raise BoundaryInputError("invalid temporal confidence")
            b = evidence.bbox
            if not (0 <= b.x1 < b.x2 <= width and 0 <= b.y1 < b.y2 <= height):
                raise BoundaryInputError("invalid temporal bbox")
            if (
                evidence.frames_since_seen < 0
                or evidence.observed != (evidence.frames_since_seen == 0)
                or not evidence.first_seen_frame_id
                <= evidence.last_seen_frame_id
                <= row.frame_id
                or not evidence.first_seen_timestamp_s
                <= evidence.last_seen_timestamp_s
                <= row.timestamp_s
                or (
                    evidence.observed
                    and (
                        evidence.last_seen_frame_id != row.frame_id
                        or evidence.last_seen_timestamp_s != row.timestamp_s
                    )
                )
            ):
                raise BoundaryInputError("inconsistent temporal presence metadata")
    if packet.stable_detections != tuple(
        d for d in window[-1].detections if d.confirmed
    ):
        raise BoundaryInputError("stable detections disagree with temporal window")
    observed = {d.continuity_key: d for d in window[-1].detections if d.observed}
    current = packet.object_frame.detections
    if len(observed) != len(current):
        raise BoundaryInputError("current and temporal observation counts disagree")
    for detection in current:
        evidence = observed.get(detection.continuity_key)
        if evidence is None or (
            evidence.track_id,
            evidence.class_id,
            evidence.class_name,
            evidence.bbox,
            evidence.raw_confidence,
            evidence.confirmed,
        ) != (
            detection.track_id,
            detection.class_id,
            detection.class_name,
            detection.bbox,
            detection.confidence,
            detection.is_stable,
        ):
            raise BoundaryInputError("current and temporal detections disagree")
    counts = (
        packet.raw_detection_count,
        packet.filtered_detection_count,
        packet.duplicate_detection_count,
    )
    if any(type(c) is not int or c < 0 for c in counts) or counts[0] != len(
        current
    ) + sum(counts[1:]):
        raise BoundaryInputError("invalid detection accounting")
