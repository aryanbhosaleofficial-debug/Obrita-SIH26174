"""Temporal correctness, identity, bounded state, replay, and ownership."""

import json
from dataclasses import FrozenInstanceError, asdict, replace

import pytest

from optimization import OptimizationSequence
from shared.config import StabilizationConfig
from shared.enums.module_status import ModuleStatus
from shared.schemas.observations import BoundingBox
from shared.schemas.optimization_packet import OptimizationOutputPacket


def test_isolated_and_low_confidence_never_confirm(object_frame, detection):
    optimizer = OptimizationSequence()
    first = optimizer.process(object_frame(0, [detection(confidence=0.7)]))
    assert not first.stable_detections
    assert not first.quality_ok and first.quality_reasons
    for i in range(1, 5):
        result = optimizer.process(object_frame(i, [detection(confidence=0.49)]))
        assert not result.stable_detections and not result.object_frame.detections
        assert result.filtered_detection_count == 1
    assert result.temporal_window[-1].detections == ()


def test_confirmation_gap_reacquisition_and_expiry(object_frame, detection):
    optimizer = OptimizationSequence(StabilizationConfig(detection_min_frames=2))
    outputs = []
    for i, seen in enumerate([True, True, False, False, True, False, False, False]):
        outputs.append(
            optimizer.process(object_frame(i, [detection()] if seen else []))
        )
    assert not outputs[0].stable_detections
    stable = outputs[1].stable_detections[0]
    assert stable.confirmed and stable.observed and stable.consecutive_seen == 2
    for i in (2, 3, 5, 6):
        held = outputs[i].stable_detections[0]
        assert held.confirmed and not held.observed and held.consecutive_seen == 0
        assert outputs[i].object_frame.detections == []
        assert not outputs[i].reliable_for_temporal_reasoning
    assert outputs[3].stable_detections[0].frames_since_seen == 2
    assert outputs[3].stable_detections[0].last_seen_frame_id == 1
    assert outputs[3].stable_detections[0].last_seen_timestamp_s == 1 / 30
    assert outputs[4].stable_detections[0].continuity_key == stable.continuity_key
    assert outputs[4].stable_detections[0].observed_frames == 3
    assert not outputs[7].stable_detections and not optimizer._stabilizer._objects


def test_tentative_confirmation_requires_consecutive_frames(object_frame, detection):
    optimizer = OptimizationSequence()
    for i, seen in enumerate([True, True, False, True, True, True]):
        packet = optimizer.process(object_frame(i, [detection()] if seen else []))
        assert bool(packet.stable_detections) == (i == 5)
    assert packet.stable_detections[0].consecutive_seen == 3


def test_ema_is_explicit_and_raw_confidence_is_preserved(object_frame, detection):
    optimizer = OptimizationSequence(
        StabilizationConfig(detection_min_frames=2, ema_alpha=0.5)
    )
    optimizer.process(object_frame(0, [detection(confidence=0.6)]))
    packet = optimizer.process(object_frame(1, [detection(confidence=1.0)]))
    assert packet.stable_detections[0].confidence == pytest.approx(0.8)
    assert packet.stable_detections[0].raw_confidence == 1.0
    assert packet.object_frame.detections[0].confidence == 1.0
    gap = optimizer.process(object_frame(2))
    assert gap.stable_detections[0].confidence == pytest.approx(0.8)
    again = optimizer.process(object_frame(3, [detection(confidence=0.5)]))
    assert again.stable_detections[0].confidence == pytest.approx(0.65)


@pytest.mark.parametrize("tracked", [True, False])
def test_multiple_instances_independent_with_reordering(
    object_frame, detection, tracked
):
    optimizer = OptimizationSequence(StabilizationConfig(detection_min_frames=2))
    a = detection(track_id=7 if tracked else None)
    b = detection(track_id=8 if tracked else None, x=100)
    c = detection(track_id=9 if tracked else None, class_id=1, x=200)
    first = optimizer.process(object_frame(0, [a, b, c]))
    second = optimizer.process(object_frame(1, [c, b, a]))
    assert second.stable_detection_count == 3
    assert {d.bbox: d.continuity_key for d in first.temporal_window[-1].detections} == {
        d.bbox: d.continuity_key for d in second.stable_detections
    }
    optimizer.process(object_frame(2, [a]))
    optimizer.process(object_frame(3, [a]))
    last = optimizer.process(object_frame(4, [a]))
    assert last.stable_detection_count == 1 and last.stable_detections[0].bbox == a.bbox


def test_exact_duplicate_suppression_keeps_distinct_track_ids(object_frame, detection):
    optimizer = OptimizationSequence(StabilizationConfig(detection_min_frames=1))
    d = detection()
    packet = optimizer.process(
        object_frame(0, [d, replace(d, confidence=0.8), detection(track_id=8)])
    )
    assert packet.raw_detection_count == 3 and packet.duplicate_detection_count == 1
    assert len(packet.object_frame.detections) == 2
    assert {d.track_id for d in packet.stable_detections} == {7, 8}


def test_untracked_duplicates_are_not_two_observations(object_frame, detection):
    optimizer = OptimizationSequence()
    d = detection(track_id=None)
    first = optimizer.process(object_frame(0, [d, d, d]))
    assert len(first.object_frame.detections) == 1
    assert not first.stable_detections
    assert first.temporal_window[-1].detections[0].observed_frames == 1


def test_ambiguous_overlap_retires_confirmed_predecessors(object_frame, detection):
    optimizer = OptimizationSequence(StabilizationConfig(detection_min_frames=2))
    a, b = detection(track_id=None), detection(track_id=None, x=50)
    for i in range(2):
        packet = optimizer.process(object_frame(i, [a, b]))
    old_keys = {d.continuity_key for d in packet.stable_detections}
    # Both new boxes match both predecessors at this deliberately permissive IoU.
    optimizer = OptimizationSequence(
        StabilizationConfig(detection_min_frames=2, matching_iou_threshold=0.05)
    )
    for i in range(2):
        optimizer.process(object_frame(i, [a, b]))
    merged = replace(a, bbox=BoundingBox(10, 10, 70, 30))
    packet = optimizer.process(object_frame(2, [merged]))
    assert not packet.stable_detections
    assert packet.object_frame.detections[0].identity_ambiguous
    assert packet.object_frame.detections[0].continuity_key not in old_keys


def test_lost_tracker_box_cannot_confirm_or_refresh(object_frame, detection):
    optimizer = OptimizationSequence(StabilizationConfig(detection_min_frames=1))
    optimizer.process(object_frame(0, [detection()]))
    for i in range(1, 4):
        packet = optimizer.process(object_frame(i, [detection(track_status="lost")]))
        assert packet.object_frame.detections == []
        if i <= 2:
            assert not packet.stable_detections[0].observed
    assert not packet.stable_detections


def test_reclassification_restarts_one_tracker_identity(object_frame, detection):
    optimizer = OptimizationSequence(StabilizationConfig(detection_min_frames=1))
    old = optimizer.process(object_frame(0, [detection()]))
    new = optimizer.process(object_frame(1, [detection(class_id=1)]))
    assert len(new.stable_detections) == 1
    assert (
        old.stable_detections[0].continuity_key
        != new.stable_detections[0].continuity_key
    )


def test_empty_zero_tolerance_and_threshold_equality(object_frame, detection):
    optimizer = OptimizationSequence(
        StabilizationConfig(
            detection_min_frames=1, max_missing_frames=0, min_detection_confidence=0.5
        )
    )
    assert optimizer.process(object_frame(0)).status == ModuleStatus.NO_DETECTION
    assert optimizer.process(
        object_frame(1, [detection(confidence=0.5)])
    ).stable_detections
    assert not optimizer.process(object_frame(2)).stable_detections


def test_reset_replay_is_exact_and_new_source_allowed(object_frame, detection):
    optimizer = OptimizationSequence()
    frames = [
        object_frame(i, [detection()] if i not in (3, 4) else []) for i in range(8)
    ]
    run1 = [asdict(optimizer.process(f)) for f in frames]
    optimizer.reset()
    run2 = [asdict(optimizer.process(f)) for f in frames]
    assert run1 == run2
    optimizer.reset()
    assert not optimizer.process(
        object_frame(0, [detection()], source_id="other")
    ).stable_detections


def test_long_running_storage_is_bounded(object_frame, detection):
    config = StabilizationConfig(history_size=5, max_detections_per_frame=4)
    optimizer = OptimizationSequence(config)
    for i in range(2000):
        # New identities every frame exercise expiry, not merely deque truncation.
        packet = optimizer.process(
            object_frame(i, [detection(track_id=4 * i + j) for j in range(4)])
        )
        assert len(packet.temporal_window) <= config.history_size
        assert len(optimizer._stabilizer._objects) <= 4 * (
            config.max_missing_frames + 1
        )
        assert len(packet.temporal_window[-1].detections) <= 12
    assert [f.frame_id for f in packet.temporal_window] == list(range(1995, 2000))
    assert not optimizer._stabilizer._pairs and not optimizer._stabilizer._interactions


def test_snapshots_own_no_images_and_cannot_be_mutated(object_frame, detection):
    optimizer = OptimizationSequence(StabilizationConfig(detection_min_frames=1))
    raw = object_frame(0, [detection()])
    before = asdict(raw)
    packet = optimizer.process(raw)
    assert isinstance(packet, OptimizationOutputPacket) and asdict(raw) == before
    snapshot = packet.stable_detections[0]
    packet.object_frame.detections[0].confidence = 0
    raw.detections[0].class_name = "mutated"
    assert snapshot.raw_confidence == 0.9 and snapshot.class_name == "class_0"
    with pytest.raises(FrozenInstanceError):
        snapshot.confidence = 0
    wire = json.dumps(asdict(packet), allow_nan=False)
    assert '"image":' not in wire
    optimizer.reset()
    assert packet.stable_detections[0] == snapshot


def test_id_gaps_advance_missing_counts_without_allocating_frames(
    object_frame, detection
):
    optimizer = OptimizationSequence(StabilizationConfig(detection_min_frames=1))
    optimizer.process(object_frame(0, [detection()]))
    short = optimizer.process(object_frame(3, [detection()]))
    assert (
        short.stable_detections and short.temporal_window[-1].missing_frames_before == 2
    )
    assert len(short.temporal_window) == 2
    old_key = short.stable_detections[0].continuity_key
    after = optimizer.process(object_frame(1000000, [detection()], timestamp_s=0.2))
    assert after.stable_detections[0].continuity_key != old_key


@pytest.mark.parametrize(
    "change",
    [
        {"image_width": 640},
        {"timestamp_s": 10.0},
    ],
)
def test_geometry_and_time_discontinuities_clear_windows(
    object_frame, detection, change
):
    optimizer = OptimizationSequence(StabilizationConfig(detection_min_frames=1))
    first = optimizer.process(object_frame(0, [detection()]))
    packet = optimizer.process(object_frame(1, [detection()], **change))
    assert len(packet.temporal_window) == 1
    assert (
        packet.stable_detections[0].continuity_key
        != first.stable_detections[0].continuity_key
    )


@pytest.mark.parametrize(
    "status", [ModuleStatus.ERROR, ModuleStatus.INVALID_INPUT, ModuleStatus.DEGRADED]
)
def test_upstream_health_never_becomes_healthy_by_accident(
    object_frame, detection, status
):
    optimizer = OptimizationSequence(StabilizationConfig(detection_min_frames=1))
    optimizer.process(object_frame(0, [detection()]))
    packet = optimizer.process(object_frame(1, [detection()], status=status))
    assert packet.status == status and not packet.quality_ok
    assert packet.quality_reasons
    if status != ModuleStatus.DEGRADED:
        assert not packet.object_frame.detections
        assert not packet.stable_detections[0].observed


def test_temporal_processing_requires_no_network(monkeypatch, object_frame, detection):
    import socket

    def forbidden(*args, **kwargs):
        raise AssertionError("network access attempted")

    monkeypatch.setattr(socket.socket, "connect", forbidden)
    monkeypatch.setattr(socket, "create_connection", forbidden)
    optimizer = OptimizationSequence()
    for i in range(4):
        packet = optimizer.process(object_frame(i, [detection()]))
    assert packet.stable_detections


def test_available_source_and_tracker_metadata_survives(object_frame, detection):
    from shared.diagnostics import Diagnostic, NoticeCode
    from shared.schemas.object_frame import ReferenceAnchor

    anchor = ReferenceAnchor("legacy", 8, (0, 0, 100, 100), 0.7, [(10, 10)])
    raw = object_frame(
        100,
        [detection(track_status="reacquired", track_quality=0.8, track_age_frames=20)],
        source_id="recording",
        session_id="experiment_2",
        reference_anchors=[anchor],
        notices=[Diagnostic(NoticeCode.OBJECT_TRACKING_DISABLED)],
        stage_timings_ms={"object_detection_ms": 4.0},
    )
    packet = OptimizationSequence(StabilizationConfig(detection_min_frames=1)).process(
        raw
    )
    assert packet.source_id == raw.source_id and packet.session_id == raw.session_id
    assert (
        packet.notices == raw.notices
        and packet.stage_timings_ms == raw.stage_timings_ms
    )
    assert packet.object_frame.reference_anchors == [anchor]
    evidence = packet.stable_detections[0]
    assert (
        evidence.track_id,
        evidence.track_status,
        evidence.track_quality,
        evidence.track_age_frames,
    ) == (7, "reacquired", 0.8, 20)
    assert evidence.first_seen_timestamp_s == raw.timestamp_s
