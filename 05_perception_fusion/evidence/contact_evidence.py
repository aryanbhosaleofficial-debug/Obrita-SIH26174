"""Quality-gated positive boundary contact; absence stays unknown."""


def extract(packet):
    return ("contact", packet.contact_confidence) if packet and packet.quality_ok and packet.hand_contact else None
