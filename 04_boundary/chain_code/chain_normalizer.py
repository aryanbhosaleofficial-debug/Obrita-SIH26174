"""Canonical cyclic start position without deleting repeated directions."""

from collections.abc import Sequence


def normalize_chain_code(chain_code: Sequence[int]) -> list[int]:
    """Booth's minimum-rotation algorithm: linear time and bounded auxiliary space."""
    seq = list(chain_code)
    if not seq:
        return []
    if any(type(value) is not int or not 0 <= value < 8 for value in seq):
        raise ValueError("chain directions must be integers in [0, 7]")
    n = len(seq)
    doubled = seq + seq
    i, j, offset = 0, 1, 0
    while i < n and j < n and offset < n:
        a, b = doubled[i + offset], doubled[j + offset]
        if a == b:
            offset += 1
            continue
        if a > b:
            i += offset + 1
            if i <= j:
                i = j + 1
        else:
            j += offset + 1
            if j <= i:
                j = i + 1
        offset = 0
    start = min(i, j)
    return seq[start:] + seq[:start]


normalize_start_point = normalize_chain_code
