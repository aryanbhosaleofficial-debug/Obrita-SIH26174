"""Distance-to-outline evidence, never proof of physical contact."""

import cv2
import numpy as np


def hand_boundary_interaction(contour, hand_data=None, *, near_threshold=20.0):
    if hand_data is None or contour is None or len(np.asarray(contour)) < 3:
        return {"available": False}
    polygon = np.asarray(contour, dtype=np.float32).reshape(-1, 1, 2)
    hands = hand_data if isinstance(hand_data, (list, tuple)) else [hand_data]
    results = []
    for index, hand in enumerate(hands):
        hand_id, coords = index, hand
        if isinstance(hand, dict):
            hand_id = hand.get("hand_id", index)
            coords = hand.get("point", hand.get("landmarks", hand.get("coordinates")))
        if coords is None:
            continue
        points = np.asarray(coords, dtype=float).reshape(-1, 2)
        if not len(points):
            continue
        distances = [
            abs(float(cv2.pointPolygonTest(polygon, tuple(map(float, p)), True)))
            for p in points
        ]
        closest = int(np.argmin(distances))
        distance = distances[closest]
        point = tuple(map(float, points[closest]))
        results.append(
            {
                "hand_id": hand_id,
                "distance_to_boundary": distance,
                "inside_boundary": cv2.pointPolygonTest(polygon, point, False) >= 0,
                "near_boundary": distance <= near_threshold,
                "closest_point": point,
                "contact_proxy": max(0.0, 1.0 - distance / near_threshold),
            }
        )
    if not results:
        return {"available": False}
    best = min(results, key=lambda row: row["distance_to_boundary"])
    return {"available": True, **best, "hands": results}


compute_hand_boundary_features = hand_boundary_interaction
