"""
Missing / occluded landmark handling.

Implementation status:
    Scaffold only.

Input:
    Smoothed landmarks with gaps

Output:
    Landmarks with explicit is_interpolated flags

Owner:
    Module 03 — Optimization Sequence (Teammate 3: spatial section)
"""

# TODO: Limit interpolation span (configurable).
# TODO: Always flag interpolated values; never present them as observed.
