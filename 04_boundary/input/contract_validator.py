"""Module 04 receiving boundary. Validates real packets; performs no segmentation."""

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
