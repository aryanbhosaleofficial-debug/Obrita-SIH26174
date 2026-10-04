"""2D geometric evidence only; overlap does not establish physical contact."""

from __future__ import annotations

import math

import cv2
import numpy as np

from perception.config import InteractionConfig
from perception.contracts import (
    BoundingBox,
    CoordinateFrame,
    Detection,
    HandObjectAssociation,
    HandObservation,
    Point2D,
)
from perception.coordinate_frame import normalized_point
from perception.utils import combine_confidence


def point_in_box(point: Point2D, box: BoundingBox) -> bool:
    return box.x1 <= point.x <= box.x2 and box.y1 <= point.y <= box.y2


def distance_to_box(point: Point2D, box: BoundingBox) -> float:
    return math.hypot(
        max(box.x1 - point.x, 0, point.x - box.x2),
        max(box.y1 - point.y, 0, point.y - box.y2),
    )


def box_contains(outer: BoundingBox, inner: BoundingBox) -> bool:
    return all(point_in_box(p, outer) for p in inner.corners)


def box_iou(a: BoundingBox, b: BoundingBox) -> float:
    overlap = max(0.0, min(a.x2, b.x2) - max(a.x1, b.x1)) * max(
        0.0, min(a.y2, b.y2) - max(a.y1, b.y1)
    )
    area_a = max(0.0, a.x2 - a.x1) * max(0.0, a.y2 - a.y1)
    area_b = max(0.0, b.x2 - b.x1) * max(0.0, b.y2 - b.y1)
    union = area_a + area_b - overlap
    return overlap / union if union > 0 else 0.0


def polygon_distance(point: Point2D, polygon: tuple[Point2D, ...]) -> float:
    contour = np.array([[p.x, p.y] for p in polygon], dtype=np.float32)
    return max(
        0.0, -cv2.pointPolygonTest(contour, (float(point.x), float(point.y)), True)
    )


def associate(
    hands: list[HandObservation],
    detections: list[Detection],
    shape: tuple[int, int],
    config: InteractionConfig,
    reference_valid: bool,
) -> list[HandObjectAssociation]:
    """Return every pair, including far/ambiguous pairs. Distances are not pixels.

    Use the transformed object polygon in rack units to avoid filling empty space
    inside a rotated polygon's enclosing box. Without calibration use x/W,y/H,
    explicitly labelled NORMALIZED_IMAGE (not orientation invariant).
    """
    output: list[HandObjectAssociation] = []
    for hi, hand in enumerate(hands):
        palm = (
            hand.reference_palm_center
            if reference_valid
            else normalized_point(hand.palm_center, shape)
        )
        points = (
            hand.reference_landmarks
            if reference_valid
            else [normalized_point(p, shape) for p in hand.landmarks]
        )
        if palm is None or points is None:
            raise ValueError("missing transformed hand coordinates")
        distances: list[float] = []
        hand_rows: list[HandObjectAssociation] = []
        for di, detection in enumerate(detections):
            polygon = (
                detection.reference_polygon
                if reference_valid
                else tuple(normalized_point(p, shape) for p in detection.bbox.corners)
            )
            if polygon is None:
                raise ValueError("missing transformed object polygon")
            point_distances = [polygon_distance(p, polygon) for p in points]
            palm_distance = polygon_distance(palm, polygon)
            minimum = min(point_distances, default=palm_distance)
            inside = sum(d <= 1e-9 for d in point_distances)
            # Overlap is the source-image AABB IoU; distance/containment use the
            # actual transformed polygon. Keep the distinction explicit.
            if hand.landmarks:
                hand_box = BoundingBox(
                    min(p.x for p in hand.landmarks),
                    min(p.y for p in hand.landmarks),
                    max(p.x for p in hand.landmarks),
                    max(p.y for p in hand.landmarks),
                )
                overlap = box_iou(hand_box, detection.bbox)
            else:
                overlap = 0.0
            geometry = max(0.0, 1.0 - minimum / config.proximity_threshold)
            row = HandObjectAssociation(
                hi,
                di,
                CoordinateFrame.RACK_RELATIVE
                if reference_valid
                else CoordinateFrame.NORMALIZED_IMAGE,
                palm_distance,
                minimum,
                inside,
                overlap,
                bool(points) and inside == len(points),
                minimum <= config.proximity_threshold,
                minimum <= config.contact_threshold,
                False,
                combine_confidence(detection.confidence, hand.confidence, geometry),
            )
            hand_rows.append(row)
            if row.near:
                distances.append(minimum)
        # Do not force a winner when several objects are equally close.
        if len(distances) > 1:
            closest = min(distances)
            ambiguous_rows = [
                row
                for row in hand_rows
                if row.near
                and row.minimum_landmark_distance <= closest + config.ambiguity_margin
            ]
            if len(ambiguous_rows) > 1:
                for row in ambiguous_rows:
                    row.ambiguous = True
        output.extend(hand_rows)
    return output
