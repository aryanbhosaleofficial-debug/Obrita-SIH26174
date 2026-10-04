"""
Pipeline orchestration.

Implementation status:
    Scaffold only.

Input:
    FramePackets from the camera; packets returned by modules 02-05

Output:
    Ordered execution 02 -> 03 -> 04 -> 05 -> Procedure FSM

Owner:
    Module 01 — Perception Core

Note:
    Numbered module directories (01_..05_) cannot be imported with a normal
    import statement. The loading strategy is an open integration decision
    (see root README.md). Do not add `from 02_yolo import ...` style imports.
"""

# TODO: Define module execution order and data hand-over.
# TODO: Decide sequential vs. threaded execution (integration decision, document it).
# TODO: Degrade gracefully when a module fails instead of crashing the whole pipeline.
# TODO: Implement graceful shutdown (release camera, flush logs).
