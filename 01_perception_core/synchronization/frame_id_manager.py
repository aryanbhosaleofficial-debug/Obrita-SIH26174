"""
Frame ID assignment.

Implementation status:
    Scaffold only.

Input:
    Raw frames in capture order

Output:
    Strictly increasing integer frame_id per source

Owner:
    Module 01 — Perception Core
"""

# TODO: Assign frame_id at capture time, before any processing.
# TODO: Never reuse a frame_id within a session.
# TODO: Record dropped frames as gaps so downstream modules can detect them.
