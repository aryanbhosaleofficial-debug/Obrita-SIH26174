"""Generic primitives, separate from Module 03's scaffold interaction tests."""

from perception.associations import associate
from perception.config import InteractionConfig
from perception.contracts import DistanceTrend, InteractionType
from perception.interaction import interaction_candidates
from perception.utils import combine_confidence


def test_generic_candidates_and_missing_identity(scene):
    detections, hands = scene
    detections[0].track_id = None
    hands[0].identity_persistent = False
    rows = associate(hands, detections, (240, 320), InteractionConfig(), False)
    candidates = interaction_candidates(detections, hands, rows)
    assert {c.interaction_type for c in candidates} == {
        InteractionType.NEAR,
        InteractionType.CONTACT,
        InteractionType.OVERLAP,
    }
    assert all(c.object_id is None and not c.identity_reliable for c in candidates)
    rows[0].ambiguous = True
    assert interaction_candidates(detections, hands, rows) == []


def test_leaving_requires_previously_near(scene):
    detections, hands = scene
    rows = associate(hands, detections, (240, 320), InteractionConfig(), False)
    rows[0].near = rows[0].contact_candidate = False
    rows[0].landmarks_inside = 0
    rows[0].hand_box_iou = 0
    rows[0].distance_trend = DistanceTrend.RETREATING
    assert interaction_candidates(detections, hands, rows) == []
    rows[0].previously_near = True
    assert (
        interaction_candidates(detections, hands, rows)[0].interaction_type
        == InteractionType.LEAVING
    )


def test_confidence_missing_components_are_not_fabricated():
    confidence = combine_confidence(0.9, None, 0.8)
    assert confidence.tracker is None and confidence.final == 0.8
    assert combine_confidence().final == 0
