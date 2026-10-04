"""
Frame reader abstraction over live camera and recorded video.

Implementation status:
    Scaffold only.

Input:
    Live camera capture or a local video file (data/videos/)

Output:
    Raw frames with end-of-stream signalling

Owner:
    Module 01 — Perception Core
"""

# TODO: Provide one interface for live and recorded sources so modules can be tested offline on recordings.
# TODO: Signal end-of-stream explicitly for video files.
# TODO: Optionally write raw frames to outputs/recordings/ when recording is enabled in config.
