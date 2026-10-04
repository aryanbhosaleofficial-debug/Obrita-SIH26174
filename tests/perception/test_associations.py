from copy import deepcopy

import pytest

from perception.associations import (
    associate,
    box_contains,
    box_iou,
    distance_to_box,
    point_in_box,
    polygon_distance,
)
from perception.config import InteractionConfig
from perception.contracts import BoundingBox, CoordinateFrame, Point2D


def test_geometry_primitives():
    box = BoundingBox(10, 20, 30, 40)
    assert point_in_box(Point2D(10, 20), box)
    assert not point_in_box(Point2D(9, 20), box)
    assert distance_to_box(Point2D(20, 30), box) == 0
    assert distance_to_box(Point2D(7, 16), box) == 5
    assert box_iou(box, box) == 1
    assert box_iou(box, BoundingBox(20, 20, 40, 40)) == pytest.approx(1 / 3)
    assert box_contains(box, BoundingBox(12, 22, 28, 38))
    assert not box_contains(box, BoundingBox(0, 0, 28, 38))


def test_near_far_multiple_hands_and_objects(scene):
    detections, hands = scene
    far = deepcopy(hands[0])
    far.hand_id = "other"
    far.palm_center = Point2D(310, 230)
    far.landmarks = [Point2D(300, 220)]
    other = deepcopy(detections[0])
    other.bbox = BoundingBox(240, 180, 280, 200)
    rows = associate(
        [hands[0], far], [detections[0], other], (240, 320), InteractionConfig(), False
    )
    assert len(rows) == 4
    assert rows[0].contact_candidate and rows[0].hand_contained
    assert rows[0].coordinate_frame == CoordinateFrame.IMAGE_DIAGONAL
    assert not rows[1].near
    assert not rows[2].near
    assert not rows[3].near
    assert rows[0].confidence.final == 0.85


def test_ambiguous_objects(scene):
    detections, hands = scene
    rows = associate(
        hands,
        [detections[0], deepcopy(detections[0])],
        (240, 320),
        InteractionConfig(),
        False,
    )
    assert all(row.ambiguous for row in rows)


def test_rack_polygon_avoids_enclosing_box_false_contact(scene):
    detections, hands = scene
    polygon = (
        Point2D(0.5, 0.1),
        Point2D(0.9, 0.5),
        Point2D(0.5, 0.9),
        Point2D(0.1, 0.5),
    )
    detections[0].reference_polygon = polygon
    hands[0].reference_landmarks = [Point2D(0.12, 0.12)]
    hands[0].reference_palm_center = Point2D(0.12, 0.12)
    rows = associate(hands, detections, (240, 320), InteractionConfig(), True)
    assert polygon_distance(Point2D(0.12, 0.12), polygon) > 0.08
    assert not rows[0].near and rows[0].landmarks_inside == 0


def test_empty_landmarks_use_palm(scene):
    detections, hands = scene
    hands[0].landmarks = []
    row = associate(hands, detections, (240, 320), InteractionConfig(), False)[0]
    assert row.near and row.contact_candidate
    assert row.landmarks_inside == 0 and not row.hand_contained
