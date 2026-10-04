"""Startup/device/offline/lifecycle checks without loading a real model."""

import sys
from dataclasses import replace
from types import SimpleNamespace

import pytest
from optimization.pipeline import OptimizationPipeline
from yolo.inference.detector import UltralyticsYoloDetector
from yolo.pipeline import YoloPipeline

from shared.config import DetectorConfig, HandTrackerConfig, PipelineConfig
from shared.enums.module_status import ModuleStatus
from shared.errors import InitializationError


@pytest.fixture
def local_config(tmp_path):
    weights = tmp_path / "local.pt"
    weights.write_bytes(b"test-fixture")
    classes = tmp_path / "classes.yaml"
    classes.write_text("classes: [{id: 0, name: vial}, {id: 1, name: tool}]")
    return DetectorConfig(model_path=weights, classes_path=classes, device="cpu")


@pytest.fixture
def install_backend(monkeypatch, raw_result):
    def install(available=False, count=1, mps=False, names=None):
        state = SimpleNamespace(loads=0, closes=0, requests=[], resets=0, fail=False)

        class Tracker:
            def reset(self):
                state.resets += 1

        class Model:
            def __init__(self, *args, **kwargs):
                state.loads += 1
                self.names = names if names is not None else {0: "vial", 1: "tool"}
                self.overrides = {}
                self.predictor = SimpleNamespace(trackers=[Tracker()], vid_path=["old"])

            def predict(self, **kwargs):
                state.requests.append(kwargs)
                if state.fail:
                    raise RuntimeError("temporary tensor failure")
                return [raw_result(shape=kwargs["source"].shape[:2])]

            track = predict

        monkeypatch.setenv("YOLO_OFFLINE", "true")
        monkeypatch.setenv("YOLO_AUTOINSTALL", "false")
        monkeypatch.setitem(
            sys.modules,
            "torch",
            SimpleNamespace(
                cuda=SimpleNamespace(
                    is_available=lambda: available, device_count=lambda: count
                ),
                backends=SimpleNamespace(mps=SimpleNamespace(is_available=lambda: mps)),
            ),
        )
        monkeypatch.setitem(sys.modules, "ultralytics", SimpleNamespace(YOLO=Model))
        monkeypatch.setitem(
            sys.modules,
            "ultralytics.utils",
            SimpleNamespace(checks=SimpleNamespace(AUTOINSTALL=False, ONLINE=False)),
        )
        return state

    return install


@pytest.mark.parametrize(
    "device,available,count,fallback,expected",
    [
        ("cpu", False, 0, False, "cpu"),
        ("auto", False, 0, False, "cpu"),
        ("auto", True, 2, False, "0"),
        ("cuda:1", True, 2, False, "1"),
        ("0", False, 0, True, "cpu"),
        ("mps", False, 0, True, "cpu"),
    ],
)
def test_device_policy(
    local_config, install_backend, device, available, count, fallback, expected
):
    install_backend(available, count)
    detector = UltralyticsYoloDetector(
        replace(local_config, device=device, cpu_fallback=fallback)
    )
    detector.initialize()
    assert detector._device == expected
    assert bool(detector.pop_warnings()) == (
        device not in {"cpu", "auto"} and expected == "cpu"
    )


def test_mps_existing_optional_backend(local_config, install_backend):
    install_backend(mps=True)
    detector = UltralyticsYoloDetector(replace(local_config, device="mps"))
    detector.initialize()
    assert detector._device == "mps"


@pytest.mark.parametrize("available,count,device", [(False, 0, "0"), (True, 1, "3")])
def test_unavailable_or_invalid_cuda_fails_at_startup(
    local_config, install_backend, available, count, device
):
    state = install_backend(available, count)
    with pytest.raises(InitializationError):
        UltralyticsYoloDetector(
            replace(local_config, device=device, cpu_fallback=False)
        ).initialize()
    assert state.loads == 0


def test_model_reuse_across_resolution_reset(local_config, install_backend, prepared):
    state = install_backend()
    with YoloPipeline(local_config) as stage:
        for _ in range(4):
            stage.process(prepared())
        stage.process(replace(prepared(width=600, height=600), reset_required=True))
        assert state.loads == 1 and state.resets == 1
        assert len(state.requests) == 5


def test_real_adapter_to_module_contract_and_filtering(
    local_config, install_backend, prepared
):
    state = install_backend()
    output = YoloPipeline(local_config).process(prepared())
    assert output.detections[0].class_name == "vial"
    assert output.detections[0].bbox_xyxy == (40, 60, 160, 180)
    kwargs = state.requests[0]
    assert kwargs["device"] == "cpu" and kwargs["conf"] == 0.5 and kwargs["iou"] == 0.45
    assert kwargs["save"] is False and kwargs["verbose"] is False


def test_model_class_mismatch_never_leaves_initialized_cache(
    local_config, install_backend
):
    state = install_backend(names={0: "wrong"})
    detector = UltralyticsYoloDetector(local_config)
    for _ in range(2):
        with pytest.raises(InitializationError, match="incompatible"):
            detector.initialize()
        assert detector._model is None and detector._class_names is None
    assert state.loads == 2


def test_backend_missing_is_actionable(local_config, monkeypatch):
    monkeypatch.setitem(sys.modules, "ultralytics", None)
    with pytest.raises(InitializationError, match="YOLO initialization failed"):
        UltralyticsYoloDetector(local_config).initialize()


def test_unreadable_or_invalid_model_reports_loader_failure(
    local_config, install_backend, monkeypatch
):
    install_backend()

    def invalid_loader(*args, **kwargs):
        raise ValueError("invalid local model format")

    monkeypatch.setattr(sys.modules["ultralytics"], "YOLO", invalid_loader)
    with pytest.raises(InitializationError, match="invalid local model format"):
        UltralyticsYoloDetector(local_config).initialize()


def test_configured_tracker_uses_only_local_yaml(
    local_config, install_backend, monkeypatch, prepared
):
    from pathlib import Path

    state = install_backend()
    monkeypatch.setattr("yolo.inference.detector.find_spec", lambda name: object())
    config = replace(
        local_config, tracking=True, tracker_path=Path("configs/yolo_tracker.yaml")
    )
    result = YoloPipeline(config).process(prepared())
    assert result.detections[0].track_id is None  # backend did not supply one
    assert state.requests[0]["persist"] is True
    assert state.requests[0]["tracker"] == str(config.tracker_path.resolve())


def test_offline_flag_conflict_does_not_import_or_load(
    local_config, install_backend, monkeypatch
):
    state = install_backend()
    monkeypatch.setenv("YOLO_OFFLINE", "false")
    with pytest.raises(InitializationError, match="YOLO_OFFLINE"):
        UltralyticsYoloDetector(local_config).initialize()
    assert state.loads == 0


def test_local_tracking_bad_yaml_and_missing_parameters(
    local_config, install_backend, tmp_path, monkeypatch
):
    install_backend()
    tracker = tmp_path / "tracker.yaml"
    detector = UltralyticsYoloDetector(
        replace(local_config, tracking=True, tracker_path=tracker)
    )
    tracker.write_text("[unclosed")
    with pytest.raises(InitializationError, match="tracker YAML"):
        detector.initialize()
    tracker.write_text("tracker_type: bytetrack")
    monkeypatch.setattr("yolo.inference.detector.find_spec", lambda name: object())
    with pytest.raises(InitializationError, match="track_high_thresh"):
        detector.initialize()


def test_unsupported_model_format_fails_without_backend(local_config):
    path = local_config.model_path.with_suffix(".bin")
    path.write_bytes(b"test")
    with pytest.raises(InitializationError, match="supports local .pt and .onnx"):
        UltralyticsYoloDetector(replace(local_config, model_path=path)).initialize()


def test_preimported_online_backend_rejected(local_config, install_backend):
    state = install_backend()
    sys.modules["ultralytics.utils"].checks.ONLINE = True
    with pytest.raises(InitializationError, match="restart with YOLO_OFFLINE"):
        UltralyticsYoloDetector(local_config).initialize()
    assert state.loads == 0


def test_autoinstall_enabled_rejected(local_config, install_backend):
    state = install_backend()
    sys.modules["ultralytics.utils"].checks.AUTOINSTALL = True
    with pytest.raises(InitializationError, match="auto-install"):
        UltralyticsYoloDetector(local_config).initialize()
    assert state.loads == 0


def test_exported_backend_metadata_uses_selected_device(
    local_config, install_backend, monkeypatch
):
    install_backend()
    weights = local_config.model_path.with_suffix(".onnx")
    weights.write_bytes(b"test-fixture")
    monkeypatch.setitem(sys.modules, "onnxruntime", SimpleNamespace())
    detector = UltralyticsYoloDetector(replace(local_config, model_path=weights))
    detector.initialize()
    assert detector._model.overrides["device"] == "cpu"


def test_raw_backend_through_actual_module01_02_03(
    local_config, install_backend, prepared
):
    state = install_backend()
    optimizer = OptimizationPipeline(
        PipelineConfig(hand_tracker=HandTrackerConfig(enabled=False, backend="none"))
    )
    try:
        with YoloPipeline(local_config) as stage:
            frame = prepared(width=803, height=401, max_width=400, color="RGB")
            objects = stage.process(frame)
            consumed = optimizer.process(frame, objects)
            assert consumed.frame_id == frame.source.frame_id
            assert consumed.timestamp_s == frame.source.timestamp_s
            assert consumed.source_id == objects.source_id == frame.source.source_id
            assert consumed.session_id == objects.session_id == frame.source.session_id
            assert consumed.object_frame.detections[0].bbox_xyxy == pytest.approx(
                (
                    20 / frame.scale_x,
                    30 / frame.scale_y,
                    80 / frame.scale_x,
                    90 / frame.scale_y,
                )
            )
            assert state.requests[0]["source"] is frame.image
            assert not objects.detections[0].is_stable
            # Healthy empty input is also consumed by the actual optimizer.
            stage.detector._model.predict = lambda **kwargs: []
            empty_frame = prepared(frame_id=14, timestamp=12.8)
            empty = stage.process(empty_frame)
            assert empty.status == ModuleStatus.NO_DETECTION
            assert optimizer.process(empty_frame, empty).object_frame.detections == []
        assert state.loads == 1
    finally:
        optimizer.close()


@pytest.mark.parametrize("tracking", [True, False])
def test_tracker_threshold_relationship_enforced_only_when_enabled(
    local_config, install_backend, tmp_path, monkeypatch, tracking
):
    from pathlib import Path

    import yaml

    state = install_backend()
    monkeypatch.setattr("yolo.inference.detector.find_spec", lambda name: object())
    tracker = yaml.safe_load(Path("configs/yolo_tracker.yaml").read_text())
    tracker["new_track_thresh"] = 0.6
    path = tmp_path / "tracker.yaml"
    path.write_text(yaml.safe_dump(tracker))
    detector = UltralyticsYoloDetector(
        replace(local_config, tracking=tracking, tracker_path=path)
    )
    if tracking:
        with pytest.raises(
            InitializationError, match="new_track_thresh.*confidence_threshold"
        ):
            detector.initialize()
        assert state.loads == 0
    else:
        detector.initialize()
        assert state.loads == 1
