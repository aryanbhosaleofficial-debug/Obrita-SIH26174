"""Active detection regressions replacing the five original skipped placeholders."""

import socket
from dataclasses import replace

import pytest
from yolo.inference.detector import UltralyticsYoloDetector
from yolo.pipeline import YoloPipeline

from shared.config import DetectorConfig
from shared.enums.module_status import ModuleStatus
from shared.errors import InitializationError
from shared.schemas.observations import BoundingBox


def test_confidence_threshold_filtering(prepared, backend, detection):
    stage = YoloPipeline(
        DetectorConfig(confidence_threshold=0.8),
        backend(
            [[replace(detection, confidence=0.79), replace(detection, confidence=0.8)]]
        ),
    )
    assert [d.confidence for d in stage.process(prepared()).detections] == [0.8]


def test_disallowed_classes_removed(prepared, backend, detection):
    stage = YoloPipeline(
        DetectorConfig(class_whitelist=[1]),
        backend([[detection, replace(detection, class_id=1, class_name="tool")]]),
    )
    assert [d.class_name for d in stage.process(prepared()).detections] == ["tool"]


def test_invalid_boxes_rejected(prepared, backend, detection):
    rows = [
        replace(detection, bbox=BoundingBox(1, 1, 1, 2)),
        replace(detection, bbox=BoundingBox(1, 1, 2, float("inf"))),
    ]
    output = YoloPipeline(DetectorConfig(), backend([rows])).process(prepared())
    assert output.status == ModuleStatus.DEGRADED and output.detections == []


def test_empty_detections_valid_object_frame(prepared, backend):
    output = YoloPipeline(DetectorConfig(), backend()).process(prepared())
    assert output.status == ModuleStatus.NO_DETECTION and output.detections == []


def test_missing_model_file_clear_error(tmp_path, monkeypatch):
    monkeypatch.setattr(
        socket.socket, "connect", lambda *a: pytest.fail("network attempted")
    )
    with pytest.raises(InitializationError, match="not found"):
        UltralyticsYoloDetector(
            DetectorConfig(model_path=tmp_path / "missing.pt")
        ).initialize()
