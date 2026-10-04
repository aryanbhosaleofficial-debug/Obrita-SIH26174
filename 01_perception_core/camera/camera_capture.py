"""
OpenCV camera capture component for SIH26174.

Implementation status:
    Scaffold only.

Input:
    Camera source (device index or local video file) from configs/camera.yaml

Output:
    Raw BGR frames (numpy.ndarray) handed to timestamp/frame-ID assignment

Owner:
    Module 01 — Perception Core
"""

# TODO: Open cv2.VideoCapture from the configured source.
# TODO: Apply requested width/height/FPS, then read back and log the values the driver actually accepted.
# TODO: Detect read failures / device disconnects and report them to the health monitor.
# TODO: Release the device cleanly on shutdown.
# TODO: Never resize, crop or colour-convert the source frame here.
