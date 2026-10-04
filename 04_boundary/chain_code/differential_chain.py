"""Differential chain coding.

The differential code is the modulo-8 first difference of consecutive Freeman
steps. For a chain ``c[0], c[1], ...``, the differential code is
``(c[i+1] - c[i]) mod 8``. This is invariant to uniform rotation of the code by
an integer offset, which is useful for comparing contours whose start point has
already been normalized.
"""

from __future__ import annotations

from typing import Sequence


def differential_chain_code(chain_code: Sequence[int]) -> list[int]:
    """Return the first-difference chain code modulo 8.

    For a normalized cyclic contour, the differential code is invariant under
    rotation by a constant offset and is the usual representation used to compare
    boundary shapes independent of start point.
    """
    if not chain_code:
        return []

    seq = list(chain_code)
    if len(seq) == 1:
        return [0]

    return [((seq[(i + 1) % len(seq)] - seq[i]) % 8) for i in range(len(seq))]
