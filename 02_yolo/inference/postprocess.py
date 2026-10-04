"""
Raw YOLO output post-processing.

Implementation status:
    Scaffold only.

Input:
    Raw YOLO outputs

Output:
    Candidate detections (box, score, class_id) still in letterboxed coordinates

Owner:
    Module 02 — YOLO
"""

# TODO: Decode boxes, scores and class ids.
# TODO: Apply NMS with the configured IoU threshold if the framework does not already do so.
# TODO: Do NOT restore coordinates here; that is preprocessing/coordinate_restore.py.
