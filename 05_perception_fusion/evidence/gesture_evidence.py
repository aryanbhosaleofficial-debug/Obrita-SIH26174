"""Only confirmed, scored gestures contribute to baseline rules."""


def extract(packet):
    gesture = packet.gesture
    return (gesture.label, gesture.confidence) if gesture and gesture.confirmed and gesture.label != "unknown" and gesture.confidence is not None else None
