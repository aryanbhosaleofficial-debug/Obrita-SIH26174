"""Active model-free tracking adapter tests, replacing footage-only placeholders.

These verify supplied identity/reset/fallback semantics, not ByteTrack physical
crossing accuracy or its unpublished lost/reacquired state. Footage evaluation
remains a deployment task described in README and the repair report.
"""

from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace

import pytest
import yaml
from optimization.pipeline import OptimizationPipeline
from yolo.config import load_config, validate_tracker
from yolo.inference.detector import UltralyticsYoloDetector
from yolo.pipeline import YoloPipeline

from shared.config import (
    ConfigurationError,
    DetectorConfig,
    HandTrackerConfig,
    PipelineConfig,
)
from shared.diagnostics import NoticeCode
from shared.enums.module_status import ModuleStatus


@pytest.fixture
def tracking_stage():
    """Replace only the external model; parsing and stage lifecycle stay real."""

    def make(frames, *, tracking=True, device="cpu", suffix=".pt", fallback=True):
        state = SimpleNamespace(calls=[], moves=[], resets=0, history=[])

        class Tracker:
            def reset(self):
                state.resets += 1
                state.history.clear()

        class Model:
            def __init__(self):
                self.frames = iter(frames)
                self.predictor = SimpleNamespace(trackers=[Tracker()], vid_path=["old"])

            def track(self, **kwargs):
                return self.infer("track", kwargs)

            def predict(self, **kwargs):
                return self.infer("predict", kwargs)

            def infer(self, mode, kwargs):
                state.calls.append((mode, kwargs))
                item = next(self.frames)
                if isinstance(item, Exception):
                    raise item
                state.history.append(item)
                return [item]

            def to(self, device):
                state.moves.append(device)
                self.predictor = None  # emulate predictor recreation / reused IDs

        config = DetectorConfig(
            model_path=Path("synthetic" + suffix),
            tracking=tracking,
            device=device,
            cpu_fallback=fallback,
        )
        adapter = UltralyticsYoloDetector(config)
        adapter._model = Model()  # explicitly injected external model fixture
        adapter._class_names = {0: "vial", 1: "tool"}
        adapter._device = device
        return YoloPipeline(config, adapter), adapter, state

    return make


def test_track_id_propagates_across_frames(tracking_stage, raw_result, prepared):
    stage, _, state = tracking_stage([raw_result(ids=[7]), raw_result(ids=[7])])
    first = stage.process(prepared())
    second = stage.process(prepared(frame_id=14, timestamp=12.8))
    assert [first.detections[0].track_id, second.detections[0].track_id] == [7, 7]
    assert all(d.identity_persistent for d in first.detections + second.detections)
    assert all(mode == "track" and kwargs["persist"] for mode, kwargs in state.calls)


def test_missing_id_is_valid_notice(tracking_stage, raw_result, prepared):
    stage, _, _ = tracking_stage([raw_result(ids=None)])
    output = stage.process(prepared())
    assert output.status == ModuleStatus.OK and output.detections[0].track_id is None
    assert not output.detections[0].identity_persistent
    assert any(n.code == NoticeCode.OBJECT_IDENTITY_UNAVAILABLE for n in output.notices)


def test_tracking_disabled_uses_predict_and_discards_id(
    tracking_stage, raw_result, prepared
):
    stage, _, state = tracking_stage([raw_result(ids=[9])], tracking=False)
    output = stage.process(prepared())
    assert output.detections[0].track_id is None
    assert not output.detections[0].identity_persistent
    assert state.calls[0][0] == "predict" and "persist" not in state.calls[0][1]
    assert any(n.code == NoticeCode.OBJECT_TRACKING_DISABLED for n in output.notices)


def test_new_backend_id_is_not_replaced(tracking_stage, raw_result, prepared):
    stage, _, _ = tracking_stage([raw_result(ids=[7]), raw_result(ids=[42])])
    assert stage.process(prepared()).detections[0].track_id == 7
    assert (
        stage.process(prepared(frame_id=14, timestamp=12.8)).detections[0].track_id
        == 42
    )


def test_empty_tracking_frame_publishes_no_lost_objects(
    tracking_stage, raw_result, prepared
):
    stage, _, _ = tracking_stage(
        [raw_result(ids=[7]), raw_result(coords=[], scores=[], classes=[])]
    )
    assert stage.process(prepared()).detections
    output = stage.process(prepared(frame_id=14, timestamp=12.8))
    assert output.status == ModuleStatus.NO_DETECTION and output.detections == []


def test_upstream_reset_clears_detector_and_optimizer_histories(
    tracking_stage, raw_result, prepared
):
    stage, adapter, state = tracking_stage([raw_result(ids=[1]) for _ in range(4)])
    optimizer = OptimizationPipeline(
        PipelineConfig(hand_tracker=HandTrackerConfig(enabled=False, backend="none"))
    )
    model = adapter._model
    try:
        for i in range(3):
            frame = prepared(frame_id=i, timestamp=i / 30)
            consumed = optimizer.process(frame, stage.process(frame))
        assert consumed.object_frame.detections[0].is_stable
        frame = replace(prepared(frame_id=3, timestamp=0.1), reset_required=True)
        objects = stage.process(frame)
        consumed = optimizer.process(frame, objects)
        assert not consumed.object_frame.detections[0].is_stable
        assert consumed.object_frame.detections[0].duration_frames == 1
        assert state.resets == 1 and len(state.history) == 1
        assert adapter._model is model and model.predictor.vid_path == [None]
    finally:
        optimizer.close()
        stage.close()


@pytest.mark.parametrize("suffix", [".pt", ".onnx"])
@pytest.mark.parametrize("fallback", [True, False])
def test_tracked_accelerator_failure_requires_reset(
    tracking_stage, raw_result, prepared, suffix, fallback
):
    stage, adapter, state = tracking_stage(
        [raw_result(ids=[1]), RuntimeError("CUDA out of memory"), raw_result(ids=[1])],
        device="0",
        suffix=suffix,
        fallback=fallback,
    )
    predictor = adapter._model.predictor
    assert stage.process(prepared()).detections[0].track_id == 1
    failed = stage.process(prepared(frame_id=14, timestamp=12.8))
    assert failed.status == ModuleStatus.ERROR and failed.detections == []
    assert "no transparent CPU" in failed.warnings[-1].details["message"]
    # Even if the external model would return a reused ID next, no inference runs.
    blocked = stage.process(prepared(frame_id=15, timestamp=12.9))
    assert blocked.status == ModuleStatus.ERROR and blocked.detections == []
    assert len(state.calls) == 2 and state.moves == []
    assert adapter._model.predictor is predictor and adapter._device == "0"
    assert not any(w.code.value == "detector_cpu_fallback" for w in failed.warnings)
    # Only an explicit coordinated reset can resume; no transparent rebuild.
    reset_frame = replace(prepared(frame_id=16, timestamp=13.0), reset_required=True)
    assert stage.process(reset_frame).status == ModuleStatus.OK
    assert state.resets == 1 and len(state.calls) == 3


@pytest.mark.parametrize("suffix", [".pt", ".onnx"])
def test_untracked_accelerator_can_retry_cpu(
    tracking_stage, raw_result, prepared, suffix
):
    stage, adapter, state = tracking_stage(
        [RuntimeError("CUDA device failure"), raw_result(ids=[1])],
        tracking=False,
        device="0",
        suffix=suffix,
    )
    output = stage.process(prepared())
    assert (
        output.status == ModuleStatus.DEGRADED and output.detections[0].track_id is None
    )
    assert [kwargs["device"] for _, kwargs in state.calls] == ["0", "cpu"]
    assert adapter._device == "cpu"
    assert state.moves == (["cpu"] if suffix == ".pt" else [])


def test_tracking_thresholds_align_in_default_config():
    root = Path(__file__).resolve().parents[2]
    config = load_config(root / "configs/yolo.yaml")
    tracker = yaml.safe_load(config.tracker_path.read_text(encoding="utf-8"))
    assert config.tracking is True and config.confidence_threshold == 0.5
    assert tracker["new_track_thresh"] == 0.5
    validate_tracker(tracker, config.confidence_threshold)


@pytest.mark.parametrize("field", ["track_high_thresh", "new_track_thresh"])
def test_tracker_threshold_above_detector_rejected(field):
    root = Path(__file__).resolve().parents[2]
    tracker = yaml.safe_load((root / "configs/yolo_tracker.yaml").read_text())
    tracker[field] = 0.6
    with pytest.raises(ConfigurationError, match=field):
        validate_tracker(tracker, 0.5)


@pytest.mark.parametrize("threshold", [0.4, 0.5])
def test_new_track_threshold_equal_or_below_detector_valid(threshold):
    root = Path(__file__).resolve().parents[2]
    tracker = yaml.safe_load((root / "configs/yolo_tracker.yaml").read_text())
    tracker["new_track_thresh"] = threshold
    validate_tracker(tracker, 0.5)
