"""
Relative-depth (pseudo-3D) representation.

Implementation status:
    Scaffold only.

Input:
    Landmarks with model z values

Output:
    Relative XYZ representation

Owner:
    Module 03 — Optimization Sequence (Teammate 3: spatial section)

Note:
    Monocular relative depth is NOT metric 3D. Only call it metric if calibrated
    depth or stereo reconstruction is actually added later.
"""

# TODO: Normalize z consistently (e.g. relative to a body reference landmark).
