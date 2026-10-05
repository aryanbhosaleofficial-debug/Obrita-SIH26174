"""Consume measured rack-relative object velocity; ignore image-space motion."""
import math


def extract(packet, detection, min_speed):
    if detection is None or packet.spatial is None or not packet.spatial.reference_frame.valid:
        return None
    velocity = detection.velocity_reference_frame
    if velocity is None or not all(math.isfinite(v) for v in (velocity.x, velocity.y)):
        return None
    return ("moving" if math.hypot(velocity.x, velocity.y) > min_speed else "stationary", detection.confidence)
