"""
Rack / payload reference-anchor extraction.

Implementation status:
    Scaffold only.

Input:
    Stable tracked detections

Output:
    ReferenceAnchor list (shared/schemas/object_frame.py)

Owner:
    Module 02 — YOLO
"""

# TODO: Select detections whose class has a reference role in configs/classes.yaml.
# TODO: Prefer the most stable anchor track.
# TODO: Report absence explicitly; never fabricate an anchor.
