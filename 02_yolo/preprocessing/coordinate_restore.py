"""
DEPRECATED / UNUSED planning scaffold; retained only for historical compatibility.
The text below is an obsolete plan, not the implemented Module 02 API.
Use yolo.pipeline.YoloPipeline: PreparedFrame -> ObjectFrame. Module 01 owns
generic preparation; Ultralytics owns model adaptation; Module 03 owns temporal
confirmation/reference calibration. No active repository import or test uses
this scaffold; do not implement a competing pipeline from its historical TODOs.

Restore detection coordinates to the original source frame.

Implementation status:
    Scaffold only.

Input:
    Boxes in letterboxed coordinates + LetterboxParams

Output:
    Boxes as (x1, y1, x2, y2) pixels in the ORIGINAL source frame

Owner:
    Module 02 — YOLO

Note:
    All coordinates passed downstream must be in original source-frame pixels,
    never letterboxed YOLO coordinates.
"""

# TODO: Remove padding, then divide by scale.
# TODO: Clip to original image bounds.
# TODO: Flag boxes that become degenerate after clipping.
