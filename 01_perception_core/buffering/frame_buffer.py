"""
Bounded frame buffer.

Implementation status:
    Scaffold only.

Input:
    FramePackets

Output:
    Lookup of recent FramePackets by frame_id (needed by Modules 03 and 04)

Owner:
    Module 01 — Perception Core
"""

# TODO: Bounded ring buffer with configurable size (camera.yaml).
# TODO: Explicit drop policy and drop counter.
# TODO: Lookup by frame_id must return None (not a different frame) when the frame was evicted.
