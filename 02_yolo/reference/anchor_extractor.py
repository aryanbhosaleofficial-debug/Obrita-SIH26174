"""
DEPRECATED / UNUSED planning scaffold; retained only for historical compatibility.
The text below is an obsolete plan, not the implemented Module 02 API.
Use yolo.pipeline.YoloPipeline: PreparedFrame -> ObjectFrame. Module 01 owns
generic preparation; Ultralytics owns model adaptation; Module 03 owns temporal
confirmation/reference calibration. No active repository import or test uses
this scaffold; do not implement a competing pipeline from its historical TODOs.

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
