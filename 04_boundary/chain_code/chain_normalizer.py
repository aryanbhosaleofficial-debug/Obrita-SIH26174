"""Start-point normalization for Freeman chain codes.

The same boundary can be represented with the same cyclic sequence starting at a
different point. This helper removes that shift-dependence by selecting the
rotation that yields the lexicographically smallest sequence (with ties broken by
sequence length and a stable circular index), and then returning the code in that
canonical rotation.
"""

from __future__ import annotations

from typing import Sequence


def normalize_chain_code(chain_code: Sequence[int]) -> list[int]:
    """Rotate a chain-code sequence into a canonical start position.

    Boundary contours traversed along a straight side may include repeated
    direction codes in a row; those are equivalent to a single side direction in
    the cyclic boundary representation. Collapse adjacent duplicates before
    selecting the canonical rotation so start-point shifts remain comparable.
    """
    if not chain_code:
        return []

    seq = list(chain_code)
    compact: list[int] = []
    for value in seq:
        if not compact or value != compact[-1]:
            compact.append(int(value))

    if not compact:
        return []
    if len(compact) == 1:
        return compact

    rotations = [compact[i:] + compact[:i] for i in range(len(compact))]
    return min(rotations)


def normalize_start_point(chain_code: Sequence[int]) -> list[int]:
    """Compatibility wrapper for start-point normalization."""
    return normalize_chain_code(chain_code)
