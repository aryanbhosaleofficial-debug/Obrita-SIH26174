"""
Geometric boundary features.

Implementation status:
    Scaffold only.

Input:
    Validated contour

Output:
    Area, perimeter, centroid, bounding box (pixels)

Owner:
    Module 04 — Boundary Detection
"""

from __future__ import annotations
import math
try:
    from ..contour.contour_validator import contour_metrics
except ImportError:
    import importlib.util
    _path = __import__("pathlib").Path(__file__).resolve().parents[1] / "contour" / "contour_validator.py"
    _spec = importlib.util.spec_from_file_location("boundary_contour_validator", _path); _module = importlib.util.module_from_spec(_spec); _spec.loader.exec_module(_module)
    contour_metrics = _module.contour_metrics

def extract_features(contour, chain_code=None):
    m = contour_metrics(contour)
    if not m["valid"]:
        return {"area": 0.0, "perimeter": 0.0, "width": 0, "height": 0, "aspect_ratio": 0.0, "centroid": None, "bbox": [0, 0, 0, 0], "solidity": 0.0, "compactness": 0.0, "chain_code_length": len(chain_code or [])}
    x, y, w, h = m["bbox"]
    return {"area": m["area"], "perimeter": m["perimeter"], "width": w, "height": h, "aspect_ratio": w / h if h else 0.0, "centroid": m["centroid"], "bbox": [x, y, w, h], "solidity": m["solidity"], "compactness": 4 * math.pi * m["area"] / (m["perimeter"] ** 2) if m["perimeter"] else 0.0, "chain_code_length": len(chain_code or [])}

geometric_features = extract_features
