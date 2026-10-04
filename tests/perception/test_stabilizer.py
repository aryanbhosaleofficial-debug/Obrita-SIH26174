from copy import deepcopy

from perception import PerceptionPipeline
from perception.contracts import BoundingBox, DistanceTrend, MotionState, Point2D
from perception.mocks import MockDetector, MockHandTracker


def scripted(config, detection_frames, hand_frames):
    return PerceptionPipeline(
        config,
        detector=MockDetector(detection_frames),
        hand_tracker=MockHandTracker(hand_frames),
    )


def test_single_false_positive_rejected_and_persistence_accepted(config, packet, scene):
    d, h = scene
    with scripted(config, [d, [], [], [], d], [h]) as pipeline:
        results = [pipeline.process(packet(i)) for i in range(5)]
    assert all(not r.interactions for r in results)
    assert not results[-1].detections[0].is_stable
    with scripted(config, [d], [h]) as pipeline:
        results = [pipeline.process(packet(i)) for i in range(5)]
    assert not results[1].detections[0].is_stable
    assert results[2].detections[0].is_stable
    assert not results[2].interactions
    assert results[3].interactions[0].duration_frames == 4
    assert results[4].interactions[0].duration_frames == 5


def test_confirmed_dropout_tolerated_without_stale_output(config, packet, scene):
    d, h = scene
    with scripted(config, [d, d, d, d, [], [], d], [h]) as pipeline:
        results = [pipeline.process(packet(i)) for i in range(7)]
    assert results[3].interactions
    assert results[4].detections == [] and results[4].interactions == []
    assert results[5].interactions == []
    assert results[6].detections[0].is_stable
    assert results[6].interactions[0].duration_frames == 5  # misses don't count
    assert results[6].detections[0].motion == MotionState.UNKNOWN


def test_expired_and_tentative_dropout(config, packet, scene):
    d, h = scene
    with scripted(config, [d, d, d, d, [], [], [], d], [h]) as pipeline:
        result = [pipeline.process(packet(i)) for i in range(8)][-1]
    assert not result.detections[0].is_stable and not result.interactions
    with scripted(config, [d, d, [], d, d, d], [h]) as pipeline:
        results = [pipeline.process(packet(i)) for i in range(6)]
    assert not results[4].detections[0].is_stable
    assert results[5].detections[0].is_stable


def test_untracked_spatial_confirmation_preserves_no_id(config, packet, scene):
    d, h = scene
    d[0].track_id = None
    h[0].identity_persistent = False
    with scripted(config, [d], [h]) as pipeline:
        result = [pipeline.process(packet(i)) for i in range(5)][-1]
    assert result.detections[0].is_stable
    assert result.detections[0].track_id is None
    assert result.detections[0].motion == MotionState.UNKNOWN
    assert all(
        i.object_id is None and not i.identity_reliable for i in result.interactions
    )


def test_ambiguous_continuity_does_not_confirm(config, packet, scene):
    d, h = scene
    d[0].track_id = None
    duplicate = deepcopy(d[0])
    with scripted(config, [[d[0], duplicate]], [h]) as pipeline:
        results = [pipeline.process(packet(i)) for i in range(10)]
    assert all(not r.interactions for r in results)
    assert all(not item.is_stable for item in results[-1].detections)


def test_motion_requires_track_and_calibration(config, packet, scene):
    d, h = scene
    moving_frames = []
    for i in range(6):
        copy = deepcopy(d)
        copy[0].bbox = BoundingBox(120 + i * 2, 80, 200 + i * 2, 160)
        moving_frames.append(copy)
    with scripted(config, moving_frames, [h]) as pipeline:
        results = [pipeline.process(packet(i)) for i in range(6)]
    assert results[0].detections[0].motion == MotionState.UNKNOWN
    assert results[-1].detections[0].motion == MotionState.MOVING
    assert results[-1].detections[0].velocity_reference_frame.x > 0
    config.reference_frame.enabled = False
    with scripted(config, moving_frames, [h]) as pipeline:
        result = [pipeline.process(packet(i)) for i in range(6)][-1]
    assert result.detections[0].motion == MotionState.UNKNOWN


def test_approach_retreat_and_leaving_history(config, packet, scene):
    d, h = scene
    hand_frames = []
    # Start near, then continuously retreat beyond the proximity threshold.
    for x in [202, 212, 224, 236, 248, 260, 272, 284]:
        hand = deepcopy(h[0])
        hand.landmarks = [Point2D(x, 120)]
        hand.palm_center = Point2D(x, 120)
        hand_frames.append([hand])
    with scripted(config, [d], hand_frames) as pipeline:
        results = [pipeline.process(packet(i)) for i in range(len(hand_frames))]
    assert results[0].associations[0].distance_trend == DistanceTrend.UNKNOWN
    assert results[2].associations[0].distance_trend == DistanceTrend.RETREATING
    assert any(
        i.interaction_type.value == "hand_leaving_object"
        for i in results[-1].interactions
    )
    with scripted(config, [d], list(reversed(hand_frames))) as pipeline:
        result = [pipeline.process(packet(i)) for i in range(len(hand_frames))][-1]
    assert result.associations[0].distance_trend == DistanceTrend.APPROACHING


def test_ema_is_capped_by_current_evidence(config, packet, scene):
    d, h = scene
    low = deepcopy(d)
    low[0].confidence = 0.6
    with scripted(config, [d, d, d, d, low], [h]) as pipeline:
        result = [pipeline.process(packet(i)) for i in range(5)][-1]
    assert result.interactions and result.interactions[0].confidence.final <= 0.6
