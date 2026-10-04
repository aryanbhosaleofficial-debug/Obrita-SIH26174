"""Observable stage, parser, configuration, failure and integration regressions."""

import socket
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from time import sleep

import numpy as np
import pytest
from optimization.pipeline import OptimizationPipeline
from yolo.config import load_config, validate_config
from yolo.inference.detector import UltralyticsYoloDetector
from yolo.inference.postprocess import BackendOutputError, parse_results
from yolo.pipeline import YoloPipeline

from shared.config import (
    ConfigurationError,
    DetectorConfig,
    HandTrackerConfig,
    PipelineConfig,
)
from shared.diagnostics import WarningCode
from shared.enums.module_status import ModuleStatus
from shared.errors import InitializationError
from shared.schemas.object_frame import ObjectFrame
from shared.schemas.observations import BoundingBox, CoordinateFrame


def test_one_object_metadata_source_coordinates_and_no_mutation(
    prepared, backend, detection
):
    frame = prepared(color="RGB")
    source_pixels, prepared_pixels = frame.source.image.copy(), frame.image.copy()
    detection.is_stable, detection.continuity_key = True, 90
    detector = backend([[detection]])
    with YoloPipeline(DetectorConfig(), detector) as stage:
        output = stage.process(frame)
    assert isinstance(output, ObjectFrame) and output.status == ModuleStatus.OK
    assert (
        output.frame_id,
        output.timestamp_s,
        output.source_id,
        output.session_id,
        output.image_width,
        output.image_height,
    ) == (13, 12.75, "camera-test", "experiment-test", 800, 400)
    assert output.detections[0].bbox == BoundingBox(40, 60, 160, 180)
    assert (
        output.detections[0].class_name == "vial"
        and output.detections[0].confidence == 0.85
    )
    assert (
        not output.detections[0].is_stable
        and output.detections[0].continuity_key is None
    )
    assert detection.is_stable and detection.continuity_key == 90
    assert np.array_equal(source_pixels, frame.source.image) and np.array_equal(
        prepared_pixels, frame.image
    )
    assert frame.image[0, 0].tolist() == [0, 0, 123]


def test_empty_and_multiobject_order_filtering(prepared, backend, detection):
    frame = prepared()
    candidates = [
        detection,
        replace(detection, class_id=1, class_name="tool"),
        replace(detection, confidence=0.49),
        replace(detection, confidence=0.5),
    ]
    with YoloPipeline(
        DetectorConfig(confidence_threshold=0.5, class_whitelist=[0]),
        backend([candidates, []]),
    ) as stage:
        output = stage.process(frame)
        empty = stage.process(frame)
    assert [d.class_id for d in output.detections] == [0, 0]
    assert [d.confidence for d in output.detections] == [0.85, 0.5]
    assert (
        empty.status == ModuleStatus.NO_DETECTION
        and not empty.detections
        and not empty.warnings
    )


@pytest.mark.parametrize(
    "image",
    [
        None,
        np.zeros((4, 4), np.uint8),
        np.zeros((4, 4, 3), np.float32),
        np.empty((0, 4, 3), np.uint8),
    ],
)
def test_malformed_prepared_image_does_not_initialize(prepared, backend, image):
    detector = backend()
    output = YoloPipeline(DetectorConfig(), detector).process(
        replace(prepared(), image=image)
    )
    assert (
        output.status == ModuleStatus.INVALID_INPUT
        and detector.initializations == detector.calls == 0
    )


@pytest.mark.parametrize("scale", [0, -1, float("nan"), float("inf"), True, 0.75])
def test_invalid_restoration_scale_rejected_before_inference(prepared, backend, scale):
    detector = backend()
    output = YoloPipeline(DetectorConfig(), detector).process(
        replace(prepared(), scale_x=scale)
    )
    assert output.status == ModuleStatus.INVALID_INPUT and detector.calls == 0


def test_missing_source_is_programming_error(prepared, backend):
    with pytest.raises(ValueError, match="source"):
        YoloPipeline(DetectorConfig(), backend()).process(
            replace(prepared(), source=None)
        )


def test_upstream_error_and_degradation_propagate(prepared, backend):
    stage = YoloPipeline(DetectorConfig(), backend())
    for status in (ModuleStatus.INVALID_INPUT, ModuleStatus.ERROR):
        assert (
            stage.process(replace(prepared(), status=status)).status
            == ModuleStatus.INVALID_INPUT
        )
    from shared.diagnostics import Diagnostic

    frame = replace(
        prepared(),
        status=ModuleStatus.DEGRADED,
        warnings=[Diagnostic(WarningCode.SOURCE_FRAME_MISSING, {"count": 1})],
    )
    assert stage.process(frame).status == ModuleStatus.DEGRADED


def test_invalid_individual_rows_clipping_and_duplicates(prepared, backend, detection):
    rows = [
        detection,
        replace(detection, bbox=BoundingBox(-2, 30, 80, 90)),
        replace(detection, bbox=BoundingBox(0, 0, float("nan"), 10)),
        replace(detection, bbox=BoundingBox(0, 0, 0, 10)),
        replace(detection, bbox=BoundingBox(900, 0, 1000, 10)),
        replace(detection, confidence=float("nan")),
        replace(detection, bbox=BoundingBox("bad", 0, 1, 1)),
        None,
        replace(detection, track_id=8),
        replace(detection, track_id=8),
    ]
    result = YoloPipeline(DetectorConfig(), backend([rows])).process(prepared())
    assert result.status == ModuleStatus.DEGRADED and len(result.detections) == 3
    assert result.detections[1].bbox.x1 == 0
    assert any(w.details.get("clipped_count") == 1 for w in result.warnings)
    assert any(w.details.get("count") == 7 for w in result.warnings)


def test_failure_after_conversion_never_leaks_partial_results(
    prepared, backend, detection
):
    class LateFailure(backend):
        def pop_warnings(self):
            raise RuntimeError("warning interface failed")

    result = YoloPipeline(DetectorConfig(), LateFailure([[detection]])).process(
        prepared()
    )
    assert result.status == ModuleStatus.ERROR and result.detections == []
    assert result.warnings[-1].code == WarningCode.DETECTOR_FAILURE


def test_startup_error_propagates_and_frame_failure_recovers(
    prepared, backend, detection
):
    class BadInit(backend):
        def initialize(self):
            raise InitializationError("bad local weights")

    with pytest.raises(InitializationError, match="bad local weights"):
        YoloPipeline(DetectorConfig(), BadInit()).process(prepared())

    class TemporaryFailure(backend):
        def detect(self, image):
            if not self.calls:
                self.calls += 1
                raise RuntimeError("temporary inference failure")
            return super().detect(image)

    detector = TemporaryFailure([[detection]])
    stage = YoloPipeline(DetectorConfig(), detector)
    assert stage.process(prepared()).status == ModuleStatus.ERROR
    assert stage.process(prepared()).status == ModuleStatus.OK
    assert detector.initializations == 1


def test_threads_serialize_and_initialize_once(prepared, backend, detection):
    class Busy(backend):
        active = False

        def detect(self, image):
            assert not self.active
            self.active = True
            sleep(0.005)
            output = super().detect(image)
            self.active = False
            return output

    detector = Busy([[detection]])
    with (
        YoloPipeline(DetectorConfig(), detector) as stage,
        ThreadPoolExecutor(max_workers=4) as pool,
    ):
        outputs = list(pool.map(stage.process, [prepared() for _ in range(8)]))
    assert all(o.status == ModuleStatus.OK for o in outputs)
    assert detector.initializations == 1 and detector.calls == 8


def test_parser_preserves_order_tracks_and_no_double_letterbox(raw_result):
    result = raw_result(
        coords=[[10, 20, 30, 40], [40, 50, 80, 90]],
        scores=[0.8, 0.7],
        classes=[1, 0],
        ids=[9, 10],
    )
    rows, invalid = parse_results([result], (200, 400), {0: "vial", 1: "tool"}, True)
    assert not invalid and [d.class_name for d in rows] == ["tool", "vial"]
    assert rows[0].bbox == BoundingBox(10, 20, 30, 40) and [
        d.track_id for d in rows
    ] == [9, 10]
    assert all(
        d.track_id is None
        for d in parse_results([result], (200, 400), result.names, False)[0]
    )


@pytest.mark.parametrize(
    "classes,ids",
    [([0.5], [1]), ([float("nan")], [1]), ([99], [1]), ([0], [0.5]), ([0], [-1])],
)
def test_parser_never_fabricates_integer_identity(raw_result, classes, ids):
    rows, invalid = parse_results(
        [raw_result(classes=classes, ids=ids)], (200, 400), {0: "vial", 1: "tool"}, True
    )
    assert rows == [] and invalid == 1


@pytest.mark.parametrize(
    "problem",
    [
        "score_count",
        "coordinate_width",
        "batch",
        "result_shape",
        "class_drift",
        "id_count",
    ],
)
def test_structural_result_corruption_is_explicit(raw_result, problem):
    result = raw_result(ids=[1])
    batch = [result]
    if problem == "score_count":
        result.boxes.conf = np.array([])
    if problem == "coordinate_width":
        result.boxes.xyxy = np.ones((1, 5))
    if problem == "batch":
        batch.append(result)
    if problem == "result_shape":
        result.orig_shape = (640, 640)
    if problem == "class_drift":
        result.names = {0: "wrong", 1: "tool"}
    if problem == "id_count":
        result.boxes.id = np.array([])
    with pytest.raises(BackendOutputError):
        parse_results(batch, (200, 400), {0: "vial", 1: "tool"}, True)


def test_standalone_yaml_relative_paths_and_snapshot(tmp_path):
    path = tmp_path / "yolo.yaml"
    path.write_text(
        "detector: {model_path: models/best.pt, classes_path: classes.yaml, device: 'cuda:0', class_whitelist: [0]}"
    )
    config = load_config(path)
    assert config.model_path == tmp_path / "models/best.pt" and config.device == "0"
    snapshot = validate_config(config)
    config.class_whitelist.append(2)
    assert snapshot.class_whitelist == [0]


@pytest.mark.parametrize(
    "values",
    [
        {"confidence_threshold": float("nan")},
        {"iou_threshold": 1.5},
        {"device": "garbage"},
        {"device": "cuda:-1"},
        {"device": "0,1"},
        {"backend": "unknown"},
        {"tracking": "false"},
    ],
)
def test_bad_standalone_config_rejected(values):
    with pytest.raises(ConfigurationError):
        YoloPipeline(DetectorConfig(**values))


def test_no_implicit_mock_production_path():
    with pytest.raises(ConfigurationError, match="injected"):
        YoloPipeline(DetectorConfig(backend="mock"))


def test_legacy_import_is_canonical():
    from perception.detector import UltralyticsYoloDetector as legacy

    assert legacy is UltralyticsYoloDetector


def test_temporary_tracker_reset_failure_is_explicit(prepared, backend, detection):
    class UnstableTracker(backend):
        failures = 1

        def reset_tracking(self):
            if self.failures:
                self.failures -= 1
                raise RuntimeError("temporary tracker reset failure")

    fake = UnstableTracker([[detection]])
    stage = YoloPipeline(DetectorConfig(), fake)
    frame = replace(prepared(), reset_required=True)
    failed = stage.process(frame)
    assert failed.status == ModuleStatus.ERROR and not failed.detections
    assert failed.warnings[-1].details["stage"] == "tracker_reset"
    assert fake.calls == 0
    assert stage.process(replace(frame, reset_required=False)).status == ModuleStatus.OK


def test_offline_actual_module03_consumer(prepared, backend, detection, monkeypatch):
    monkeypatch.setattr(
        socket.socket, "connect", lambda *args: pytest.fail("unexpected network")
    )
    frame = prepared()
    config = PipelineConfig(
        detector=DetectorConfig(),
        hand_tracker=HandTrackerConfig(enabled=False, backend="none"),
    )
    optimization = OptimizationPipeline(config)
    try:
        output = YoloPipeline(config.detector, backend([[detection]])).process(frame)
        consumed = optimization.process(frame, output)
        assert consumed.object_frame.detections[0].bbox == BoundingBox(40, 60, 160, 180)
        assert (
            consumed.source_id == output.source_id
            and consumed.frame_id == output.frame_id
        )
        assert (
            consumed.observations.association_coordinate_frame
            == CoordinateFrame.IMAGE_DIAGONAL
        )
    finally:
        optimization.close()


def test_failed_frame_drains_backend_warnings(prepared, backend, detection):
    class RetryFailure(backend):
        def __init__(self, frames):
            super().__init__(frames)
            self.warnings = []

        def detect(self, image):
            if self.calls == 0:
                self.calls += 1
                self.warnings = ["detector_cpu_fallback"]
                raise RuntimeError("CPU retry failed")
            return super().detect(image)

        def pop_warnings(self):
            warnings, self.warnings = self.warnings, []
            return warnings

    fake = RetryFailure([[detection]])
    with YoloPipeline(DetectorConfig(), fake) as stage:
        failed = stage.process(prepared())
        healthy = stage.process(prepared(frame_id=14, timestamp=12.8))
    assert failed.status == ModuleStatus.ERROR and not failed.detections
    assert any(w.code == WarningCode.CPU_FALLBACK for w in failed.warnings)
    assert healthy.status == ModuleStatus.OK and not healthy.warnings
    assert fake.initializations == 1


def test_empty_external_boxes(raw_result):
    result = raw_result(coords=[], scores=[], classes=[])
    assert parse_results([result], (200, 400), result.names, False) == ([], 0)
    result.boxes = None
    assert parse_results([result], (200, 400), result.names, False) == ([], 0)


@pytest.mark.parametrize("score", [-0.1, 1.1, float("inf"), True])
def test_invalid_external_confidence_is_discarded(raw_result, score):
    result = raw_result(scores=[score])
    assert parse_results([result], (200, 400), result.names, False) == ([], 1)


def test_clipped_numpy_geometry_serializes(prepared, backend, detection):
    import json
    from dataclasses import asdict

    candidate = replace(
        detection,
        bbox=BoundingBox(np.float32(-1), np.float32(2), np.float32(80), np.float32(90)),
    )
    output = YoloPipeline(DetectorConfig(), backend([[candidate]])).process(prepared())
    assert all(type(v) is float for v in output.detections[0].bbox_xyxy)
    assert json.loads(json.dumps(asdict(output)))["detections"][0]["bbox"]["x1"] == 0
