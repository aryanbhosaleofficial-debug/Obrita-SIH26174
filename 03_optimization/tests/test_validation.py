"""Invalid configuration/contracts fail before any temporal state is changed."""

from dataclasses import replace

import pytest
from optimization.config import load_config
from optimization.input.input_validator import OptimizationInputError
from optimization.optimizer import OptimizationSequence

from shared.config import ConfigurationError, StabilizationConfig
from shared.schemas.observations import BoundingBox


@pytest.mark.parametrize(
    "changes",
    [
        {"detection_min_frames": 0},
        {"detection_min_frames": True},
        {"history_size": 2},
        {"history_size": 0},
        {"history_size": 2.5},
        {"max_missing_frames": -1},
        {"max_missing_frames": True},
        {"min_detection_confidence": -0.1},
        {"min_detection_confidence": 1.1},
        {"min_detection_confidence": float("nan")},
        {"min_detection_confidence": True},
        {"ema_alpha": 0},
        {"ema_alpha": float("inf")},
        {"matching_iou_threshold": 0},
        {"max_time_gap_s": 0},
        {"confidence_aggregation": "unknown"},
        {"max_detections_per_frame": 0},
    ],
)
def test_invalid_configuration(changes):
    with pytest.raises(ConfigurationError):
        OptimizationSequence(StabilizationConfig(**changes))


@pytest.mark.parametrize(
    "changes",
    [
        {"frame_id": -1},
        {"frame_id": True},
        {"frame_id": 1.5},
        {"timestamp_s": -1},
        {"timestamp_s": float("nan")},
        {"timestamp_s": float("inf")},
        {"timestamp_s": "1"},
        {"image_width": 0},
        {"image_height": -1},
        {"image_width": True},
        {"source_id": ""},
        {"session_id": None},
        {"status": "ok"},
        {"detections": None},
        {"detections": [None]},
        {"warnings": ["bad"]},
        {"notices": None},
        {"stage_timings_ms": {"inference": float("nan")}},
        {"reference_anchors": [None]},
    ],
)
def test_invalid_packet_does_not_advance_state(object_frame, detection, changes):
    optimizer = OptimizationSequence(StabilizationConfig(detection_min_frames=1))
    before = optimizer.process(object_frame(0, [detection()]))
    broken = replace(object_frame(1, [detection()]), **changes)
    with pytest.raises(OptimizationInputError):
        optimizer.process(broken)
    after = optimizer.process(object_frame(1, [detection()]))
    assert (
        after.stable_detections[0].continuity_key
        == before.stable_detections[0].continuity_key
    )
    assert after.stable_detections[0].observed_frames == 2


@pytest.mark.parametrize(
    "changes",
    [
        {"confidence": float("nan")},
        {"confidence": float("inf")},
        {"confidence": -1},
        {"confidence": 1.1},
        {"confidence": None},
        {"class_id": -1},
        {"class_name": ""},
        {"track_id": True},
        {"track_id": -3},
        {"bbox": (1, 2, 3, 4)},
        {"bbox": BoundingBox(0, 0, 0, 1)},
        {"bbox": BoundingBox(10, 10, 0, 0)},
        {"bbox": BoundingBox(-1, 0, 20, 20)},
        {"bbox": BoundingBox(0, 0, 321, 20)},
        {"bbox": BoundingBox(0, 0, float("nan"), 20)},
        {"track_status": "invented"},
        {"track_status": []},
        {"frames_since_seen": -1},
        {"track_quality": 2},
    ],
)
def test_malformed_detection_rejected(object_frame, detection, changes):
    with pytest.raises(OptimizationInputError):
        OptimizationSequence().process(
            object_frame(0, [replace(detection(), **changes)])
        )


def test_incorrect_type_and_conflicting_identity(object_frame, detection):
    optimizer = OptimizationSequence()
    with pytest.raises(TypeError, match="ObjectFrame"):
        optimizer.process({})
    with pytest.raises(OptimizationInputError, match="track_id"):
        optimizer.process(object_frame(0, [detection(), detection(x=100)]))
    with pytest.raises(OptimizationInputError, match="max_detections"):
        OptimizationSequence(StabilizationConfig(max_detections_per_frame=1)).process(
            object_frame(0, [detection(), detection(track_id=8)])
        )


@pytest.mark.parametrize(
    "changes",
    [
        {"frame_id": 0},
        {"timestamp_s": 0.0},
        {"source_id": "other"},
        {"session_id": "other"},
    ],
)
def test_order_and_stream_switch_rejected_without_reset(
    object_frame, detection, changes
):
    optimizer = OptimizationSequence()
    optimizer.process(object_frame(0, [detection()]))
    with pytest.raises(OptimizationInputError):
        optimizer.process(replace(object_frame(1, [detection()]), **changes))
    # Failed input did not consume frame 1.
    result = optimizer.process(object_frame(1, [detection()]))
    assert result.temporal_window[-1].detections[0].consecutive_seen == 2


def test_configuration_snapshot_does_not_change_midstream():
    config = StabilizationConfig()
    optimizer = OptimizationSequence(config)
    config.history_size = 99
    assert optimizer.config.history_size == 12


@pytest.mark.parametrize(
    "content",
    [
        "[]",
        "stabilization: []",
        "typo: {}",
        "stabilization: {typo: 2}",
        "stabilization: {history_size: 1}",
    ],
)
def test_bad_owner_configuration(tmp_path, content):
    path = tmp_path / "optimization.yaml"
    path.write_text(content, encoding="utf-8")
    with pytest.raises(ConfigurationError):
        load_config(path)
