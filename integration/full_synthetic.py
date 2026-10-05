"""Full-system test inputs: inference fakes and explicitly simulated semantic actions."""
from dataclasses import replace

import cv2

from integration.synthetic import scene, configure
from pose_tracking.synthetic import SyntheticLandmarkBackend
from shared.schemas.observations import BoundingBox, Detection, Point2D
from shared.schemas.activity_event import ActivityEvent


def rotate_xy(x, y, rotation):
    """Normalized physical point rotated clockwise in the camera image."""
    return {0: (x, y), 90: (1 - y, x), 180: (1 - x, 1 - y)}[rotation]


def inputs(config, count, session, rotation=0, *, box_demo=False):
    frames, detector, hands = scene(count, session)
    if box_demo:
        for index, packet in enumerate(frames):
            packet.image[:] = (35, 40, 45)
            cv2.rectangle(packet.image, (65, 85), (125, 145), (0, 0, 230), -1)
            cv2.rectangle(packet.image, (195, 85), (255, 145), (0, 220, 220), -1)
            detector.frames[index] = [
                Detection(0, "red_box", .9, BoundingBox(65, 85, 125, 145), track_id=7, identity_persistent=True),
                Detection(1, "yellow_box", .9, BoundingBox(195, 85, 255, 145), track_id=8, identity_persistent=True)]
    config = configure(config)
    config.reference_frame.corners_normalized = [list(rotate_xy(x, y, rotation))
                                                for x, y in ((0, 0), (1, 0), (1, 1), (0, 1))]
    if rotation:
        # Inference fakes use source pixels. Keep geometries paired with rotated pixels.
        for index, packet in enumerate(frames):
            old_w, old_h = packet.width, packet.height
            rotated = cv2.rotate(packet.image, cv2.ROTATE_90_CLOCKWISE if rotation == 90 else cv2.ROTATE_180)
            h, w = rotated.shape[:2]
            def point(p):
                x, y = rotate_xy(p.x / old_w, p.y / old_h, rotation)
                return Point2D(x * w, y * h)
            for detection in detector.frames[index]:
                pts = [point(p) for p in detection.bbox.corners]
                detection.bbox = BoundingBox(min(p.x for p in pts), min(p.y for p in pts),
                                             max(p.x for p in pts), max(p.y for p in pts))
            for hand in hands.frames[index]:
                hand.landmarks = [point(p) for p in hand.landmarks]
                hand.palm_center = point(hand.palm_center)
            frames[index] = replace(packet, image=rotated, width=w, height=h)
    for packet in frames:
        packet.metadata["rotation_demo_degrees"] = rotation
    return config, frames, detector, hands


class RotatedLandmarkBackend(SyntheticLandmarkBackend):
    def __init__(self, rotation=0):
        self.rotation = rotation

    def detect(self, image_bgr, timestamp_s):
        result = super().detect(image_bgr, timestamp_s)
        def landmark(p):
            x, y = rotate_xy(p.x, p.y, self.rotation)
            return replace(p, x=x, y=y)
        return replace(result, body=tuple(landmark(p) for p in result.body) if result.body else None,
                       hands=tuple(replace(h, landmarks=tuple(landmark(p) for p in h.landmarks)) for h in result.hands))


class SemanticScenario:
    """Simulated HAR outputs selected from procedure data, not a perception claim.

    Use scenario=fusion to bypass this simulator and consume actual Module 05
    rule outputs. Scenario index patterns only describe test ordering.
    """
    def __init__(self, definition, scenario="correct", interval_frames=12):
        self.definition, self.interval = definition, interval_frames
        if scenario != "correct" and len(definition.steps) != 4:
            raise ValueError("error scenarios require the four-step demo configuration")
        self.sequence = {"correct": tuple(range(len(definition.steps))), "wrong-order": (2,),
                         "skip": (0, 2), "repeated": (0, 0), "recovery": (0, 2, 1, 2, 3)}[scenario]

    def event(self, packet):
        index = packet.frame_id // self.interval
        if index >= len(self.sequence) or packet.frame_id % self.interval != self.interval - 1:
            return None
        step = self.definition.steps[self.sequence[index]]
        return ActivityEvent(f"simulated-{packet.session_id}-{index}", step.expected_activity,
                             packet.frame_id, packet.timestamp_s, packet.frame_id, packet.frame_id,
                             packet.timestamp_s, packet.timestamp_s, confidence=.95,
                             target_object_class=step.target_object,
                             metadata={"source_id": packet.source_id, "session_id": packet.session_id,
                                       "confirmed": True, "emitted": True, "synthetic": True,
                                       "simulation_boundary": "semantic HAR output", "procedure_id": self.definition.experiment_id})
