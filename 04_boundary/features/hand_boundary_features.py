"""
Hand-boundary features.

Implementation status:
    Scaffold only.

Input:
    Hand landmarks + target contour

Output:
    Hand-to-boundary distances / overlap

Owner:
    Module 04 — Boundary Detection
"""

from __future__ import annotations
import cv2
import numpy as np

def hand_boundary_interaction(contour, hand_data=None, *, near_threshold=20.0):
    if hand_data is None or contour is None or len(np.asarray(contour)) < 3: return {"available": False}
    polygon = np.asarray(contour, dtype=np.float32).reshape(-1, 1, 2); hands = hand_data if isinstance(hand_data, (list, tuple)) else [hand_data]; results = []
    for index, hand in enumerate(hands):
        hand_id, coords = index, hand
        if isinstance(hand, dict): hand_id, coords = hand.get("hand_id", index), hand.get("point", hand.get("landmarks", hand.get("coordinates")))
        if coords is None: continue
        points = np.asarray(coords, dtype=float).reshape(-1, 2)
        if not len(points): continue
        distances = [abs(float(cv2.pointPolygonTest(polygon, (float(p[0]), float(p[1])), True))) for p in points]; i = int(np.argmin(distances)); p = points[i]; distance = distances[i]
        inside = cv2.pointPolygonTest(polygon, (float(p[0]), float(p[1])), False) >= 0
        results.append({"hand_id": hand_id, "distance_to_boundary": distance, "inside_boundary": bool(inside), "near_boundary": distance <= near_threshold, "closest_point": [float(p[0]), float(p[1])], "contact_proxy": max(0.0, 1.0 - distance / near_threshold) if near_threshold else 0.0})
    return {"available": True, **results[0], "hands": results} if results else {"available": False}

compute_hand_boundary_features = hand_boundary_interaction
