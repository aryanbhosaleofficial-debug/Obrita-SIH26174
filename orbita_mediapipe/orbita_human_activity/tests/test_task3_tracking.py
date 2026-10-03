"""Controlled synthetic Task 3 tests; no real-camera performance claim."""

import unittest

import numpy as np

from orbita_human_activity.features.temporal_features import TemporalFeatureBuilder, TemporalSequenceManager
from orbita_human_activity.schemas.feature_types import FrameFeatureVector
from orbita_human_activity.schemas.spatial_types import CoordinateSpace, Landmark3D, PersonPose3D
from orbita_human_activity.schemas.tracking_types import TrackState
from orbita_human_activity.tracking.tracker import MultiPersonTracker


def pose(x: float, timestamp_ms: int, include_centroid: bool = True) -> PersonPose3D:
    landmarks = []
    if include_centroid:
        landmarks.extend([
            Landmark3D(23, "LEFT_HIP", x - 0.1, 0.0, 2.0, visibility=0.9, coordinate_space=CoordinateSpace.MEDIAPIPE_WORLD),
            Landmark3D(24, "RIGHT_HIP", x + 0.1, 0.0, 2.0, visibility=0.9, coordinate_space=CoordinateSpace.MEDIAPIPE_WORLD),
        ])
    return PersonPose3D(
        timestamp_ms=timestamp_ms,
        frame_index=timestamp_ms // 33,
        world_landmarks=landmarks,
        bbox_2d=(x - 0.15, -0.4, x + 0.15, 0.4),
    )


class TestTask3Tracking(unittest.TestCase):
    def test_one_person_and_two_person_initialization(self):
        tracker = MultiPersonTracker(max_persons=2)
        one = tracker.update([pose(-0.5, 0)], 0)
        self.assertEqual(set(one.active_tracks), {"HUMAN_1"})
        tracker = MultiPersonTracker(max_persons=2)
        two = tracker.update([pose(0.5, 0), pose(-0.5, 0)], 0)
        self.assertEqual(set(two.active_tracks), {"HUMAN_1", "HUMAN_2"})
        self.assertAlmostEqual(two.active_tracks["HUMAN_1"].last_centroid_3d[0], -0.5)

    def test_detection_array_reorder_and_crossing_do_not_change_ids(self):
        tracker = MultiPersonTracker(max_persons=2)
        tracker.update([pose(-0.6, 0), pose(0.6, 0)], 0)
        tracker.update([pose(-0.5, 33), pose(0.5, 33)], 33)
        crossing = tracker.update([pose(0.45, 66), pose(-0.45, 66)], 66)
        self.assertAlmostEqual(crossing.active_tracks["HUMAN_1"].last_centroid_3d[0], -0.45)
        self.assertAlmostEqual(crossing.active_tracks["HUMAN_2"].last_centroid_3d[0], 0.45)

    def test_temporary_occlusion_and_reappearance(self):
        tracker = MultiPersonTracker(max_persons=2, max_lost_frames=3)
        tracker.update([pose(-0.4, 0)], 0)
        tracker.update([pose(-0.4, 33)], 33)
        coast = tracker.update([], 66)
        self.assertEqual(coast.active_tracks["HUMAN_1"].state, TrackState.COASTING)
        self.assertEqual(coast.active_tracks["HUMAN_1"].last_observed_timestamp_ms, None)
        back = tracker.update([pose(-0.35, 99)], 99)
        self.assertEqual(back.active_tracks["HUMAN_1"].state, TrackState.CONFIRMED)
        self.assertEqual(back.active_tracks["HUMAN_1"].last_observed_timestamp_ms, 99)

    def test_track_deletion_and_slot_reuse_are_explicit(self):
        tracker = MultiPersonTracker(max_persons=2, max_lost_frames=1)
        tracker.update([pose(-0.4, 0)], 0)
        tracker.update([pose(-0.4, 33)], 33)
        tracker.update([], 66)
        deleted = tracker.update([], 99)
        self.assertNotIn("HUMAN_1", deleted.active_tracks)
        reappeared = tracker.update([pose(-0.4, 132)], 132)
        self.assertIn("HUMAN_1", reappeared.active_tracks)
        self.assertGreater(reappeared.active_tracks["HUMAN_1"].track_id, 1)

    def test_missing_centroid_is_not_fabricated(self):
        tracker = MultiPersonTracker(max_persons=2)
        result = tracker.update([pose(0.0, 0, include_centroid=False)], 0)
        self.assertIsNone(result.active_tracks["HUMAN_1"].last_centroid_3d)

    def test_independent_feature_histories_and_sequence_buffers(self):
        builder = TemporalFeatureBuilder()
        seq = TemporalSequenceManager(sequence_length=2, step_size=1)
        h1_a = builder.extract_frame_features(pose(-0.4, 0))
        h1_a.person_id = "HUMAN_1"
        h2_a = builder.extract_frame_features(pose(0.4, 0))
        h2_a.person_id = "HUMAN_2"
        h1_b = builder.extract_frame_features(pose(-0.3, 33))
        h1_b.person_id = "HUMAN_1"
        h2_b = builder.extract_frame_features(pose(0.3, 33))
        h2_b.person_id = "HUMAN_2"
        first = seq.add_frame_feature(h1_a)
        self.assertIsNone(first)
        self.assertIsNone(seq.add_frame_feature(h2_a))
        h1_window = seq.add_frame_feature(h1_b)
        h2_window = seq.add_frame_feature(h2_b)
        self.assertEqual(h1_window.person_id, "HUMAN_1")
        self.assertEqual(h2_window.person_id, "HUMAN_2")
        self.assertNotEqual(h1_window.features.tolist(), h2_window.features.tolist())


if __name__ == "__main__":
    unittest.main()
