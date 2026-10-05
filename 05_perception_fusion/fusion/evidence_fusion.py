"""Ordered configurable all/any evidence rules with explicit support scores."""
from .confidence_fusion import aggregate


def candidates(evidence, config):
    output = []
    def matches(source, values):
        return source in evidence and ("*" in values or evidence[source][0] in values)
    for rule in config["activities"]["rules"]:
        if not all(matches(s, v) for s, v in rule["all"].items()):
            continue
        supporting = set(rule["all"])
        alternatives = {s for s, v in rule["any"].items() if matches(s, v)}
        if rule["any"] and not alternatives:
            continue
        supporting |= alternatives
        support = {s: evidence[s] for s in supporting}
        confidence = aggregate(support, config["confidence"]["weights"])
        if confidence >= config["confidence"]["min_event_confidence"]:
            output.append((rule["label"], confidence, rule["name"], {s: support[s][1] for s in sorted(support)}))
    return output
