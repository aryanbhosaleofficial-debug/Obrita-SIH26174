"""Shared result identity, temporal confirmation and continuous event semantics."""
import pytest
from fusion.pipeline import FusionPipeline
from shared.schemas.activity_event import ActivityEvent


def test_uses_shared_schema(upstream):
    result = FusionPipeline().process(*upstream())
    assert isinstance(result, ActivityEvent)
    assert result.activity_label == "unknown"
    assert result.confidence == 0
    assert not result.metadata["emitted"]


def test_start_end_frames_set(upstream):
    pipeline = FusionPipeline()
    for fid in range(10, 13):
        result = pipeline.process(*upstream(fid))
    assert result.start_frame_id == 10
    assert result.end_frame_id == result.frame_id == 12
    assert result.start_timestamp_s == pytest.approx(10 / 30)
    assert result.end_timestamp_s == result.timestamp_s == 12 / 30
    assert result.metadata["source_id"] == "unit"
    assert result.target_object_track_id == 7


def test_no_duplicate_events(upstream):
    pipeline = FusionPipeline()
    results = [pipeline.process(*upstream(fid)) for fid in range(20)]
    emitted = [r for r in results if r.metadata["emitted"]]
    assert len(emitted) == 1
    assert all(r.event_id == emitted[0].event_id for r in results[2:])


def test_labels_match_procedure_vocabulary(upstream):
    from procedure.procedure_loader import load_procedure
    pipeline = FusionPipeline()
    definition = load_procedure("procedures/demo_experiment.yaml", "configs")
    assert {s.expected_activity for s in definition.steps} <= set(pipeline.config["activities"]["labels"])


def test_no_procedure_validation_in_fusion(upstream):
    result = FusionPipeline().process(*upstream())
    assert not hasattr(result, "step_id")
    assert not hasattr(result, "correct")


def test_single_noisy_frame_does_not_confirm(upstream):
    pipeline = FusionPipeline()
    for fid in range(8):
        event = pipeline.process(*upstream(fid, contact=(fid == 1)))
        assert event.activity_label == "unknown"


def test_target_changes_do_not_accumulate_hits(upstream):
    pipeline = FusionPipeline()
    for fid in range(8):
        event = pipeline.process(*upstream(fid, track=7 + fid % 2))
        assert event.activity_label == "unknown"


def test_short_missing_gap_does_not_duplicate_and_long_gap_rearms(upstream):
    pipeline = FusionPipeline()
    for fid in range(3):
        result = pipeline.process(*upstream(fid))
    first = result.event_id
    opt, boundary = upstream(3)
    opt.object_frame.detections = []
    opt.quality_ok = False
    assert pipeline.process(opt, boundary).activity_label == "unknown"
    result = pipeline.process(*upstream(4))
    assert result.event_id == first and not result.metadata["emitted"]
    for fid in range(5, 8):
        pipeline.process(*upstream(fid, contact=False))
    for fid in range(8, 11):
        result = pipeline.process(*upstream(fid))
    assert result.metadata["emitted"] and result.event_id != first


def test_gaps_and_timeouts_cannot_confirm_old_evidence(upstream):
    pipeline = FusionPipeline()
    pipeline.process(*upstream(0))
    pipeline.process(*upstream(1))
    assert pipeline.process(*upstream(20)).activity_label == "unknown"
    pipeline.reset()
    pipeline.process(*upstream(0))
    pipeline.process(*upstream(1))
    assert pipeline.process(*upstream(2, timestamp=10)).activity_label == "unknown"


def test_replay_and_session_change_require_reset(upstream):
    pipeline = FusionPipeline()
    pipeline.process(*upstream(0))
    with pytest.raises(ValueError, match="strictly"):
        pipeline.process(*upstream(0))
    opt, boundary = upstream(1)
    opt.session_id = "other"
    opt.object_frame.session_id = "other"
    with pytest.raises(ValueError, match="reset"):
        pipeline.process(opt, boundary)
    pipeline.reset()
    assert pipeline.process(*upstream(0)).activity_label == "unknown"


def test_event_ids_remain_unique_after_reset(upstream):
    pipeline = FusionPipeline()
    for fid in range(3):
        first = pipeline.process(*upstream(fid))
    pipeline.reset()
    for fid in range(3):
        second = pipeline.process(*upstream(fid))
    assert first.event_id != second.event_id


def test_invalid_packet_breaks_confirmation(upstream):
    pipeline = FusionPipeline()
    pipeline.process(*upstream(0))
    pipeline.process(*upstream(1))
    opt, boundary = upstream(2)
    boundary.frame_id = 99
    with pytest.raises(ValueError):
        pipeline.process(opt, boundary)
    assert pipeline.process(*upstream(3)).activity_label == "unknown"


def test_new_activity_confirms_without_losing_pending_hits(upstream):
    from shared.enums.boundary_state import BoundaryState
    pipeline = FusionPipeline()
    for fid in range(3):
        pipeline.process(*upstream(fid))
    for fid in range(3, 6):
        opt, boundary = upstream(fid, contact=False)
        boundary.boundary_state = BoundaryState.SEPARATING
        boundary.state_confirmed = True
        result = pipeline.process(opt, boundary)
    assert result.activity_label == "release_object"
    assert result.metadata["emitted"]
