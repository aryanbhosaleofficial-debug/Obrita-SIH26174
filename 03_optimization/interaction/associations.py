"""2D geometric evidence only; overlap does not establish physical contact."""

from __future__ import annotations

import math

import cv2
import numpy as np

from shared.config import InteractionConfig
from shared.geometry import isotropic_point
from shared.schemas.observations import (
    BoundingBox,
    CoordinateFrame,
    Detection,
    HandObjectAssociation,
    HandObservation,
    Point2D,
)
from shared.utils.observation import combine_confidence


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
    inside a rotated polygon's enclosing box. Fallback uses x/diagonal,y/diagonal,
    explicitly labelled IMAGE_DIAGONAL. Context objects remain observable.
    """
    thresholds = config.rack_relative if reference_valid else config.image_diagonal
    output: list[HandObjectAssociation] = []
    contours = []
    for detection in detections:
        detection.is_context = detection.class_name in config.context_classes
        polygon = (
            detection.reference_polygon
            if reference_valid
            else tuple(isotropic_point(p, shape) for p in detection.bbox.corners)
        )
        if polygon is None:
            raise ValueError("missing transformed object polygon")
        contours.append(np.array([[p.x, p.y] for p in polygon], dtype=np.float32))

    def distance(point, contour):
        return max(
            0.0, -cv2.pointPolygonTest(contour, (float(point.x), float(point.y)), True)
        )

    for hi, hand in enumerate(hands):
        palm = (
            hand.reference_palm_center
            if reference_valid
            else isotropic_point(hand.palm_center, shape)
        )
        points = (
            hand.reference_landmarks
            if reference_valid
            else [isotropic_point(p, shape) for p in hand.landmarks]
        )
        if palm is None or points is None:
            raise ValueError("missing transformed hand coordinates")
        distances: list[float] = []
        hand_rows: list[HandObjectAssociation] = []
        hand_box = (
            BoundingBox(
                min(p.x for p in hand.landmarks),
                min(p.y for p in hand.landmarks),
                max(p.x for p in hand.landmarks),
                max(p.y for p in hand.landmarks),
            )
            if hand.landmarks
            else None
        )
        for di, detection in enumerate(detections):
            contour = contours[di]
            point_distances = [distance(p, contour) for p in points]
            palm_distance = distance(palm, contour)
            minimum = min(point_distances, default=palm_distance)
            inside = sum(d <= 1e-9 for d in point_distances)
            # Overlap is the source-image AABB IoU; distance/containment use the
            # actual transformed polygon. Keep the distinction explicit.
            overlap = box_iou(hand_box, detection.bbox) if hand_box is not None else 0.0
            geometry = max(0.0, 1.0 - minimum / thresholds.proximity_threshold)
            row = HandObjectAssociation(
                hi,
                di,
                CoordinateFrame.RACK_RELATIVE
                if reference_valid
                else CoordinateFrame.IMAGE_DIAGONAL,
                palm_distance,
                minimum,
                inside,
                overlap,
                bool(points) and inside == len(points),
                minimum <= thresholds.proximity_threshold,
                minimum <= thresholds.contact_threshold,
                False,
                combine_confidence(detection.confidence, hand.confidence, geometry),
            )
            row.hand_key, row.object_key = hand.continuity_key, detection.continuity_key
            row.is_context = detection.is_context
            row.distance_units = (
                "rack_units" if reference_valid else "image_diagonal_units"
            )
            hand_rows.append(row)
            if row.near and not row.is_context:
                distances.append(minimum)
        # Do not force a winner when several objects are equally close.
        if len(distances) > 1:
            closest = min(distances)
            ambiguous_rows = [
                row
                for row in hand_rows
                if row.near
                and not row.is_context
                and row.minimum_landmark_distance
                <= closest + thresholds.ambiguity_margin
            ]
            if len(ambiguous_rows) > 1:
                for row in ambiguous_rows:
                    row.ambiguous = True
        output.extend(hand_rows)
    return output
