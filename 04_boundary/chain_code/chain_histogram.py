"""Chain direction histogram utilities."""

from __future__ import annotations

from collections.abc import Sequence


def chain_histogram(chain_code: Sequence[int], *, bins: int = 8) -> list[float]:
    """Return a normalized 8-bin histogram for a Freeman chain code.

    Each bin counts the number of occurrences of a code value. The result is
    normalized to sum to 1.0 for non-empty chain codes.
    """
    if not chain_code:
        return [0.0] * bins

    hist = [0.0] * bins
    for value in chain_code:
        if 0 <= value < bins:
            hist[value] += 1.0
    total = sum(hist)
    if total == 0:
        return [0.0] * bins
    return [count / total for count in hist]
