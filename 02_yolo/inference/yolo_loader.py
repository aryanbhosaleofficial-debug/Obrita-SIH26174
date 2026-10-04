"""
DEPRECATED / UNUSED planning scaffold; retained only for historical compatibility.
The text below is an obsolete plan, not the implemented Module 02 API.
Use yolo.pipeline.YoloPipeline: PreparedFrame -> ObjectFrame. Module 01 owns
generic preparation; Ultralytics owns model adaptation; Module 03 owns temporal
confirmation/reference calibration. No active repository import or test uses
this scaffold; do not implement a competing pipeline from its historical TODOs.

YOLO model loader.

Implementation status:
    Scaffold only.

Input:
    Local model path from configs/yolo.yaml (weights stored in 02_yolo/models/)

Output:
    Loaded model object + model metadata (class names, input size)

Owner:
    Module 02 — YOLO
"""

# TODO: Load weights from the local path only; fail with a clear error if the file is missing.
# TODO: Never trigger an automatic model download (offline requirement).
# TODO: Select device (CPU/GPU) from config.
