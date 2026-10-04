"""
DEPRECATED / UNUSED planning scaffold; retained only for historical compatibility.
The text below is an obsolete plan, not the implemented Module 02 API.
Use yolo.pipeline.YoloPipeline: PreparedFrame -> ObjectFrame. Module 01 owns
generic preparation; Ultralytics owns model adaptation; Module 03 owns temporal
confirmation/reference calibration. No active repository import or test uses
this scaffold; do not implement a competing pipeline from its historical TODOs.

Input normalization for YOLO.

Implementation status:
    Scaffold only.

Input:
    Letterboxed image

Output:
    Model-ready tensor/array

Owner:
    Module 02 — YOLO
"""

# TODO: Apply channel order (BGR -> RGB) and dtype/scale required by the chosen model.
