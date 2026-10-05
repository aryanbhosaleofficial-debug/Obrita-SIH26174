"""Configured conflict policies report disagreement without altering upstream."""
from fusion.config import load_config
from fusion.pipeline import FusionPipeline
from shared.enums.boundary_state import BoundaryState
from shared.schemas.observations import Point2D


def test_optimization_vs_boundary_conflict(upstream):
    pipeline = FusionPipeline()
    for fid in range(5):
        opt, boundary = upstream(fid)
        boundary.crosscheck_agrees = False
        result = pipeline.process(opt, boundary)
        assert result.activity_label == "unknown"
        assert result.conflicts


def test_conflicts_recorded_in_event(upstream):
    cfg = load_config()
    cfg["conflict_resolution"]["policy"] = "prefer_confirmed_boundary"
    pipeline = FusionPipeline(cfg)
    for fid in range(3):
        opt, boundary = upstream(fid)
        boundary.crosscheck_agrees = False
        result = pipeline.process(opt, boundary)
    assert result.activity_label == "touch_object"
    assert result.conflicts
    assert result.metadata["emitted"]


def test_agreeing_evidence_no_conflict(upstream):
    pipeline = FusionPipeline()
    for fid in range(3):
        opt, boundary = upstream(fid)
        boundary.crosscheck_agrees = True
        result = pipeline.process(opt, boundary)
    assert result.activity_label == "touch_object"
    assert not result.conflicts


def test_derived_motion_conflict_without_upstream_crosscheck(upstream):
    opt, boundary = upstream()
    opt.object_frame.detections[0].velocity_reference_frame = Point2D(0.2, 0)
    boundary.boundary_state = BoundaryState.STATIONARY
    event = FusionPipeline().process(opt, boundary)
    assert event.activity_label == "unknown"
    assert event.conflicts
