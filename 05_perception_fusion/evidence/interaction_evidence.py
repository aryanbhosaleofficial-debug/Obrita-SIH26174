"""Current target-index interactions only; scores stay optional when unavailable."""


def extract(packet, index, priority):
    candidates = [i for i in packet.interactions if i.detection_index == index and i.observed and not i.ambiguous and i.frames_since_seen == 0 and i.confidence.final is not None and i.interaction_type.value in priority]
    item = min(candidates, key=lambda i: (priority.index(i.interaction_type.value), -i.confidence.final), default=None)
    return (item.interaction_type.value, item.confidence.final) if item else None
