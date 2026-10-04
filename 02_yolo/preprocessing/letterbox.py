"""
DEPRECATED / UNUSED planning scaffold; retained only for historical compatibility.
The text below is an obsolete plan, not the implemented Module 02 API.
Use yolo.pipeline.YoloPipeline: PreparedFrame -> ObjectFrame. Module 01 owns
generic preparation; Ultralytics owns model adaptation; Module 03 owns temporal
confirmation/reference calibration. No active repository import or test uses
this scaffold; do not implement a competing pipeline from its historical TODOs.

Letterbox preprocessing.

Implementation status:
    Scaffold only.

Input:
    FramePacket.image (original source frame)

Output:
    Resized + padded image and LetterboxParams (scale, pad_x, pad_y)

Owner:
    Module 02 — YOLO
"""

# TODO: Compute scale and padding for the model input size.
# TODO: Return the parameters needed for coordinate restoration.
# TODO: Operate on a copy; the source frame must never be modified.
