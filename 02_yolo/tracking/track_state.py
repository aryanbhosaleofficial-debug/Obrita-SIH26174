"""
DEPRECATED / UNUSED planning scaffold; retained only for historical compatibility.
The text below is an obsolete plan, not the implemented Module 02 API.
Use yolo.pipeline.YoloPipeline: PreparedFrame -> ObjectFrame. Module 01 owns
generic preparation; Ultralytics owns model adaptation; Module 03 owns temporal
confirmation/reference calibration. No active repository import or test uses
this scaffold; do not implement a competing pipeline from its historical TODOs.

Track state definitions and transitions.

Implementation status:
    Scaffold only.

Input:
    Track lifecycle events

Output:
    Track status values

Owner:
    Module 02 — YOLO
"""

# TODO: Implement valid transitions tentative -> confirmed -> lost -> reacquired/removed.
# TODO: Values must match TrackStatus documented in shared/schemas/object_frame.py.
