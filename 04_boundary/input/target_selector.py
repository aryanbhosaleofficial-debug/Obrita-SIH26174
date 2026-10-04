"""
Boundary target selection.

Implementation status:
    Scaffold only.

Input:
    Interaction candidates + ObjectFrame (inside OptimizationOutputPacket)

Output:
    Target object track_id and bbox

Owner:
    Module 04 — Boundary Detection
"""

from __future__ import annotations

def select_target(*, object_bbox=None, person_bbox=None, interaction_candidates=None):
    """Return the upstream-selected object bbox; Module 04 does not detect objects."""
    if object_bbox is None:
        return {"available": False, "reason": "no YOLO object bbox"}
    return {"available": True, "object_bbox": tuple(object_bbox), "person_bbox": person_bbox,
            "selection_rule": "use the object selected by upstream interaction association"}
