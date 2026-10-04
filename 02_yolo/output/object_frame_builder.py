"""
DEPRECATED / UNUSED planning scaffold; retained only for historical compatibility.
The text below is an obsolete plan, not the implemented Module 02 API.
Use yolo.pipeline.YoloPipeline: PreparedFrame -> ObjectFrame. Module 01 owns
generic preparation; Ultralytics owns model adaptation; Module 03 owns temporal
confirmation/reference calibration. No active repository import or test uses
this scaffold; do not implement a competing pipeline from its historical TODOs.

ObjectFrame builder.

Implementation status:
    Scaffold only.

Input:
    DetectedObject list, ReferenceAnchor list, source FramePacket metadata

Output:
    ObjectFrame (shared/schemas/object_frame.py)

Owner:
    Module 02 — YOLO
"""

# TODO: Assemble the shared ObjectFrame schema.
# TODO: Copy frame_id and timestamp_s from the FramePacket unchanged.
# TODO: Set ModuleStatus (OK / DEGRADED / NO_DETECTION / ERROR).
