"""
DEPRECATED / UNUSED planning scaffold; retained only for historical compatibility.
The text below is an obsolete plan, not the implemented Module 02 API.
Use yolo.pipeline.YoloPipeline: PreparedFrame -> ObjectFrame. Module 01 owns
generic preparation; Ultralytics owns model adaptation; Module 03 owns temporal
confirmation/reference calibration. No active repository import or test uses
this scaffold; do not implement a competing pipeline from its historical TODOs.

Confidence and class filtering.

Implementation status:
    Scaffold only.

Input:
    Restored candidate detections

Output:
    Detections above threshold and of allowed classes

Owner:
    Module 02 — YOLO
"""

# TODO: Drop detections below the configured confidence threshold.
# TODO: Keep only classes allowed in configs/classes.yaml / yolo.yaml.
# TODO: Support optional per-class thresholds.
