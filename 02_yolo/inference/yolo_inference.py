"""
DEPRECATED / UNUSED planning scaffold; retained only for historical compatibility.
The text below is an obsolete plan, not the implemented Module 02 API.
Use yolo.pipeline.YoloPipeline: PreparedFrame -> ObjectFrame. Module 01 owns
generic preparation; Ultralytics owns model adaptation; Module 03 owns temporal
confirmation/reference calibration. No active repository import or test uses
this scaffold; do not implement a competing pipeline from its historical TODOs.

YOLO inference component for SIH26174.

Implementation status:
    Scaffold only.

Input:
    Preprocessed (letterboxed, normalized) image derived from FramePacket.image

Output:
    Raw YOLO detections (letterboxed coordinates)

Owner:
    Module 02 — YOLO
"""

# TODO: Run the loaded model on one preprocessed image.
# TODO: Return raw outputs together with the LetterboxParams used.
# TODO: Report inference errors as ModuleStatus instead of raising into the pipeline loop.
