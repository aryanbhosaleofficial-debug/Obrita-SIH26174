"""
Body pose inference (MediaPipe-style).

Implementation status:
    Scaffold only.

Input:
    Operator ROI

Output:
    Body landmarks (x, y in original-frame pixels; z = relative depth)

Owner:
    Module 03 — Optimization Sequence (Teammate 3: spatial section)
"""

# TODO: Run a locally stored pose model (no runtime download).
# TODO: Map ROI coordinates back to original-frame pixels.
# TODO: Treat z as relative depth only; it is NOT metric 3D.
