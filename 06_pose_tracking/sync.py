"""Frame pairing and read-only adapters for future hand-object fusion.

Both branches copy (source_id, session_id, frame_id, timestamp_s) from the same
FramePacket, so pairing is an exact key comparison: no nearest-timestamp guess.
Nothing here performs fusion or activity reasoning.
"""

from __future__ import annotations

from pose_tracking.contracts import LEFT, RIGHT, FrameKey, PoseFrame
from pose_tracking.landmarks import PALM_INDICES

from shared.schemas.object_frame import ObjectFrame
from shared.schemas.observations import HandObservation, Point2D, PoseObservation
from shared.schemas.prepared_frame import PreparedFrame


class FrameSyncError(ValueError):
    """Two packets that must describe the same source frame do not."""


def frame_key(packet) -> FrameKey:
    """FrameKey of a PreparedFrame (via its source), ObjectFrame or PoseFrame."""
    if isinstance(packet, PoseFrame):
        return packet.key
    if isinstance(packet, PreparedFrame):
        packet = packet.source
        if packet is None:
            raise FrameSyncError("PreparedFrame has no source FramePacket")
    try:
        return FrameKey(
            packet.source_id, packet.session_id, packet.frame_id, packet.timestamp_s
        )
    except AttributeError as exc:
        raise TypeError(f"no frame identity on {type(packet).__name__}") from exc


def is_synchronized(*packets) -> bool:
    return len({frame_key(p) for p in packets}) <= 1


def require_synchronized(*packets) -> FrameKey:
    keys = {frame_key(p) for p in packets}
    if len(keys) != 1:
        raise FrameSyncError(
            f"packets describe different frames: {sorted(map(str, keys))}"
        )
    return keys.pop()


def to_pose_observation(
    pose: PoseFrame, *, include_held: bool = False
) -> PoseObservation | None:
    """Shared PoseObservation (source pixels) for consumers of the existing contract."""
    if not pose.body_landmarks or (not pose.body_detected and not include_held):
        return None
    # Legacy observation has no per-joint validity mask. Do not export invalid
    # joints as trusted positions or shrink the indexed backend topology.
    if not all(p.is_valid for p in pose.body_landmarks):
        return None
    return PoseObservation(
        [Point2D(p.x, p.y) for p in pose.body_landmarks],
        confidence=pose.body_score,
        reference_landmarks=([Point2D(*p.rack_xy) for p in pose.body_landmarks]
                             if all(p.rack_xy is not None for p in pose.body_landmarks) else None),
    )


def to_hand_observations(
    pose: PoseFrame, *, include_held: bool = False
) -> list[HandObservation]:
    """Shared HandObservation list. Handedness uses the anatomical title-case label.

    ``hand_id`` is the per-frame side label, not a persistent identity, so
    ``identity_persistent`` stays False exactly as for Module 03's hand tracker.
    Mirror correction is already complete; mirrored_input is metadata only and
    downstream consumers must not swap the anatomical handedness again.
    """
    output = []
    for hand in pose.hands:
        if not hand.observed and not include_held:
            continue
        if not all(p.is_valid for p in hand.landmarks):
            continue
        cx, cy = hand.palm_center
        output.append(
            HandObservation(
                hand_id=hand.handedness.lower()
                if hand.handedness in (LEFT, RIGHT)
                else None,
                handedness=hand.handedness.title()
                if hand.handedness in (LEFT, RIGHT)
                else None,
                confidence=None,
                landmarks=[Point2D(p.x, p.y) for p in hand.landmarks],
                palm_center=Point2D(cx, cy),
                handedness_confidence=hand.handedness_score,
                mirrored_input=pose.input_mirrored,
                reference_landmarks=([Point2D(*p.rack_xy) for p in hand.landmarks]
                                     if all(p.rack_xy is not None for p in hand.landmarks) else None),
                reference_palm_center=(
                    Point2D(sum(hand.landmarks[i].rack_xy[0] for i in PALM_INDICES) / len(PALM_INDICES),
                            sum(hand.landmarks[i].rack_xy[1] for i in PALM_INDICES) / len(PALM_INDICES))
                    if all(p.rack_xy is not None for p in hand.landmarks) else None
                ),
            )
        )
    return output


def pair_with_objects(
    pose: PoseFrame, objects: ObjectFrame
) -> tuple[PoseFrame, ObjectFrame]:
    """Validated (PoseFrame, ObjectFrame) pair for a future interaction-fusion stage."""
    require_synchronized(pose, objects)
    if (pose.image_width, pose.image_height) != (
        objects.image_width,
        objects.image_height,
    ):
        raise FrameSyncError(
            "pose and object coordinates refer to different image sizes"
        )
    return pose, objects
