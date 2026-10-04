"""
DEPRECATED / UNUSED planning scaffold; retained only for historical compatibility.
The text below is an obsolete plan, not the implemented Module 02 API.
Use yolo.pipeline.YoloPipeline: PreparedFrame -> ObjectFrame. Module 01 owns
generic preparation; Ultralytics owns model adaptation; Module 03 owns temporal
confirmation/reference calibration. No active repository import or test uses
this scaffold; do not implement a competing pipeline from its historical TODOs.

Multi-object tracker.

Implementation status:
    Scaffold only.

Input:
    Validated detections per frame

Output:
    Detections associated with persistent track_id values

Owner:
    Module 02 — YOLO
"""

# TODO: Choose the tracking approach (integration decision; must run fully offline).
# TODO: Associate detections across frames.
# TODO: Keep track_id persistent while an object stays visible.
