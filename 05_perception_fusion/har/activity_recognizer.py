"""Deterministic priority selection; insufficient evidence is unknown."""


def recognize(candidates):
    return candidates[0] if candidates else ("unknown", 0.0, None, {})
