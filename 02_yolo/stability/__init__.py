"""
DEPRECATED / UNUSED planning scaffold; retained only for historical compatibility.
The text below is an obsolete plan, not the implemented Module 02 API.
Use yolo.pipeline.YoloPipeline: PreparedFrame -> ObjectFrame. Module 01 owns
generic preparation; Ultralytics owns model adaptation; Module 03 owns temporal
confirmation/reference calibration. No active repository import or test uses
this scaffold; do not implement a competing pipeline from its historical TODOs.

Multi-frame detection confirmation.

Owner:
    Module 02 — YOLO

Note:
    The top-level directory name starts with a digit, so it cannot be imported
    with a normal `import` statement. The integration-time loading strategy is
    documented in the root README.md. Do not add imports such as
    `from 02_yolo import ...`.
"""
