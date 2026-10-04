"""
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
