"""
DEPRECATED / UNUSED planning scaffold; retained only for historical compatibility.
The text below is an obsolete plan, not the implemented Module 02 API.
Use yolo.pipeline.YoloPipeline: PreparedFrame -> ObjectFrame. Module 01 owns
generic preparation; Ultralytics owns model adaptation; Module 03 owns temporal
confirmation/reference calibration. No active repository import or test uses
this scaffold; do not implement a competing pipeline from its historical TODOs.

Bounding box validation.

Implementation status:
    Scaffold only.

Input:
    Filtered detections

Output:
    Valid detections; rejected detections are counted and logged

Owner:
    Module 02 — YOLO
"""

# TODO: Reject zero/negative-area boxes.
# TODO: Reject non-finite values.
# TODO: Check boxes lie inside the original frame after clipping.
