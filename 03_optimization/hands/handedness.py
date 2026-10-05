"""
Handedness resolution.

Implementation status:
    Scaffold only.

Input:
    Hand landmarks + model handedness output

Output:
    Left/right label with score

Owner:
    Module 03 — Optimization Sequence (Teammate 3: spatial section)
"""

# Inactive scaffold: anatomical mirror correction is implemented at the
# producer boundary in MediaPipeHandTracker (hand_tracker.py). mirrored_input
# is provenance only; consumers must not swap the shared handedness again.
# Module 06's LandmarkStabilizer separately guards EMA against label flicker.
