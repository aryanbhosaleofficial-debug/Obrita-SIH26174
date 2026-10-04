"""
PreparedFrame -> local object detection (optional backend IDs) -> ObjectFrame.

Canonical entry point: yolo.pipeline.YoloPipeline. Temporal stability and rack
calibration belong to Module 03; legacy planning leaves are inactive.

Owner:
    Module 02 â€” YOLO

Note:
    The top-level directory name starts with a digit, so it cannot be imported
    with a normal `import` statement. The integration-time loading strategy is
    documented in the root README.md. Do not add imports such as
    `from 02_yolo import ...`.
"""

# ruff: noqa: N999 -- numeric owner directory is imported via the yolo alias
