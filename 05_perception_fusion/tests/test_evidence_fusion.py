"""Validation, normalization and configurable evidence scoring."""
from copy import deepcopy
import math
import pytest
from fusion.config import load_config, validate_config
from fusion.pipeline import FusionPipeline
from fusion.fusion.confidence_fusion import aggregate
from shared.config import ConfigurationError
from shared.enums.module_status import ModuleStatus


@pytest.mark.parametrize("field,value", [("frame_id", 9), ("timestamp_s", 2.0), ("target_track_id", 2)])
def test_packets_matched_by_frame_and_track(upstream, field, value):
    opt, boundary = upstream()
    setattr(boundary, field, value)
    with pytest.raises(ValueError, match="mismatch"):
        FusionPipeline().process(opt, boundary)


@pytest.mark.parametrize("which", ["optimization", "boundary"])
@pytest.mark.parametrize("status", [ModuleStatus.ERROR, ModuleStatus.INVALID_INPUT])
def test_invalid_status_rejected(upstream, which, status):
    opt, boundary = upstream()
    (opt if which == "optimization" else boundary).status = status
    with pytest.raises(ValueError, match="rejects"):
        FusionPipeline().process(opt, boundary)


@pytest.mark.parametrize("value", [-0.1, 1.1, float("nan"), float("inf"), True, None])
def test_confidence_range_validated(upstream, value):
    opt, boundary = upstream()
    boundary.confidence = value
    with pytest.raises(ValueError, match="confidence"):
        FusionPipeline().process(opt, boundary)


def test_missing_evidence_not_negative(upstream):
    pipeline = FusionPipeline()
    for fid in range(3):
        event = pipeline.process(*upstream(fid))
    assert event.activity_label == "touch_object"
    assert event.confidence == pytest.approx(aggregate(
        {"object": ("sample_container", 0.9), "contact": ("contact", 0.8), "boundary": ("contact", 0.9)},
        pipeline.config["confidence"]["weights"]))
    assert "gesture" not in event.evidence_summary


def test_weights_from_config(upstream):
    cfg = load_config()
    cfg["confidence"]["weights"]["object"] = 1.0
    pipeline = FusionPipeline(cfg)
    for fid in range(3):
        event = pipeline.process(*upstream(fid))
    assert event.confidence == pytest.approx((0.9 + 0.8 * 0.15 + 0.9 * 0.3) / 1.45)


@pytest.mark.parametrize("change", ["hits", "weight", "label", "policy", "missing", "null", "rule"])
def test_invalid_config_rejected(change):
    cfg = load_config()
    if change == "hits":
        cfg["temporal"]["confirmation_min_hits"] = 1
    elif change == "weight":
        cfg["confidence"]["weights"]["object"] = -1
    elif change == "label":
        cfg["activities"]["labels"] = ["unknown"]
    elif change == "policy":
        cfg["conflict_resolution"]["policy"] = "magic"
    elif change == "missing":
        del cfg["evidence"]["min_confidence"]["motion"]
    elif change == "null":
        cfg["temporal"]["confirmation_window"] = None
    else:
        cfg["activities"]["rules"][0]["all"]["cloud"] = ["anything"]
    with pytest.raises(ConfigurationError):
        validate_config(cfg)


def test_nested_identity_and_no_mutation(upstream):
    opt, boundary = upstream()
    before = deepcopy((opt, boundary))
    event = FusionPipeline().process(opt, boundary)
    assert (opt, boundary) == before
    opt.spatial.frame_id = 9
    with pytest.raises(ValueError, match="nested"):
        FusionPipeline().process(opt, boundary)


def test_low_quality_or_unstable_or_held_is_unknown(upstream):
    for mode in ("quality", "stable", "held", "ambiguous"):
        pipeline = FusionPipeline()
        for fid in range(5):
            opt, boundary = upstream(fid)
            d = opt.object_frame.detections[0]
            if mode == "quality":
                opt.quality_ok = False
            elif mode == "stable":
                d.is_stable = False
            elif mode == "held":
                d.frames_since_seen = 1
            else:
                d.identity_ambiguous = True
            result = pipeline.process(opt, boundary)
            assert result.activity_label == "unknown"
            assert not result.metadata["emitted"]


def test_configured_gesture_rule(upstream):
    from shared.schemas.optimization_packet import GestureResult
    cfg = load_config()
    cfg["activities"]["labels"].append("grasp")
    cfg["activities"]["rules"].insert(0, {"name": "grasp", "label": "grasp",
                                          "all": {"object": ["*"], "gesture": ["grasp"]}, "any": {}})
    pipeline = FusionPipeline(cfg)
    for fid in range(3):
        opt, boundary = upstream(fid, contact=False)
        opt.gesture = GestureResult("grasp", 0.9, confirmed=True)
        event = pipeline.process(opt, boundary)
    assert event.activity_label == "grasp"


def test_nested_source_mismatch_rejected(upstream):
    opt, boundary = upstream()
    opt.object_frame.session_id = "different"
    with pytest.raises(ValueError, match="source/session mismatch"):
        FusionPipeline().process(opt, boundary)


def test_rack_motion_is_consumed_and_uncalibrated_motion_ignored(upstream):
    from shared.schemas.observations import Point2D
    pipeline = FusionPipeline()
    for fid in range(3):
        opt, boundary = upstream(fid)
        opt.object_frame.detections[0].velocity_reference_frame = Point2D(0.2, 0)
        result = pipeline.process(opt, boundary)
    assert result.activity_label == "move_object"
    assert "motion" in result.evidence_summary
    pipeline.reset()
    for fid in range(3):
        opt, boundary = upstream(fid)
        opt.object_frame.detections[0].velocity_reference_frame = Point2D(0.2, 0)
        opt.spatial.reference_frame.valid = False
        result = pipeline.process(opt, boundary)
    assert result.activity_label == "touch_object"
    assert "motion" not in result.metadata["evidence"]


def test_rotation_rule_consumes_confirmed_upstream_packets(upstream):
    from shared.enums.boundary_state import BoundaryState
    pipeline = FusionPipeline()
    for fid in range(3):
        opt, boundary = upstream(fid)
        boundary.boundary_state = BoundaryState.ROTATING
        result = pipeline.process(opt, boundary)
    assert result.activity_label == "rotate_object"
    assert result.evidence_summary["boundary"] == 0.9


def test_approach_rule_consumes_target_interaction(upstream):
    from shared.schemas.observations import InteractionPrimitive, InteractionType, ObservationConfidence
    pipeline = FusionPipeline()
    for fid in range(3):
        opt, boundary = upstream(fid, contact=False)
        opt.interactions = [InteractionPrimitive(
            InteractionType.NEAR, "hand", "7", "sample_container",
            ObservationConfidence(final=0.8), detection_index=0)]
        result = pipeline.process(opt, boundary)
    assert result.activity_label == "approach_object"
