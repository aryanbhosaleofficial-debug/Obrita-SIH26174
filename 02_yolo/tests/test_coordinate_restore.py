"""Upstream scale restoration and avoiding a second Ultralytics letterbox undo.

Ultralytics Results.xyxy are already in its input image pixels. The horizontal/
vertical padding fixtures below describe that returned contract, rather than an
independent letterbox implementation belonging to Module 01 or this stage.
"""

from dataclasses import replace

import pytest
from yolo.inference.postprocess import (
    BackendOutputError,
    clamp_source_box,
    parse_results,
)
from yolo.pipeline import YoloPipeline

from shared.config import DetectorConfig
from shared.enums.module_status import ModuleStatus
from shared.schemas.observations import BoundingBox


def test_no_padding(prepared, backend, detection):
    frame = prepared(max_width=None)
    assert (
        YoloPipeline(DetectorConfig(), backend([[detection]]))
        .process(frame)
        .detections[0]
        .bbox
        == detection.bbox
    )


def test_horizontal_letterbox_padding(raw_result):
    # Portrait image: the backend has already removed its left/right model padding.
    result = raw_result(coords=[[5, 10, 20, 30]], shape=(400, 200))
    output, invalid = parse_results([result], (400, 200), result.names, False)
    assert not invalid and output[0].bbox == BoundingBox(5, 10, 20, 30)


def test_vertical_letterbox_padding(raw_result):
    # Landscape image: no extra subtraction of model top/bottom padding is valid.
    result = raw_result(coords=[[10, 5, 30, 20]], shape=(200, 400))
    output, invalid = parse_results([result], (200, 400), result.names, False)
    assert not invalid and output[0].bbox == BoundingBox(10, 5, 30, 20)


def test_bbox_touching_image_edge(prepared, backend, detection):
    frame = prepared()
    box = replace(detection, bbox=BoundingBox(0, 0, 400, 200))
    assert YoloPipeline(DetectorConfig(), backend([[box]])).process(frame).detections[
        0
    ].bbox == BoundingBox(0, 0, 800, 400)


def test_invalid_bbox(prepared, backend, detection):
    box = replace(detection, bbox=BoundingBox(10, 10, 1, 1))
    assert (
        YoloPipeline(DetectorConfig(), backend([[box]])).process(prepared()).detections
        == []
    )


def test_letterbox_restore_round_trip(prepared, backend, raw_result):
    # Emulate a framework-restored prediction, then apply Module 01 scale once.
    frame = prepared(width=803, height=401, max_width=400)
    original = BoundingBox(40, 60, 160, 180)
    result = raw_result(
        coords=[
            [
                original.x1 * frame.scale_x,
                original.y1 * frame.scale_y,
                original.x2 * frame.scale_x,
                original.y2 * frame.scale_y,
            ]
        ],
        shape=frame.image.shape[:2],
    )
    predictions, _ = parse_results([result], frame.image.shape[:2], result.names, False)
    actual = (
        YoloPipeline(DetectorConfig(), backend([predictions]))
        .process(frame)
        .detections[0]
        .bbox
    )
    assert (actual.x1, actual.y1, actual.x2, actual.y2) == pytest.approx(
        (40, 60, 160, 180), abs=1e-9
    )


def test_source_boundary_roundoff_is_clamped(prepared, backend, detection):
    frame = prepared(width=745, height=480, max_width=640)
    h, w = frame.image.shape[:2]
    full = replace(detection, bbox=BoundingBox(0, 0, w, h))
    assert frame.source_detection(full).bbox.y2 > 480  # reviewer reproducer
    result = YoloPipeline(DetectorConfig(), backend([[full]])).process(frame)
    b = result.detections[0].bbox
    assert 0 <= b.x1 < b.x2 <= 745 and 0 <= b.y1 < b.y2 <= 480
    assert b == BoundingBox(0, 0, 745, 480) and result.status == ModuleStatus.OK


@pytest.mark.parametrize(
    "box",
    [
        BoundingBox(0, 0, 746, 480),
        BoundingBox(0, -0.001, 745, 480),
        BoundingBox(0, 0, 0, 480),
    ],
)
def test_source_clamp_does_not_conceal_transform_errors(box):
    with pytest.raises(BackendOutputError):
        clamp_source_box(box, 745, 480)
