"""Unit tests for multi-person tracking association and identity persistence."""

import unittest
import numpy as np

from orbita_human_activity.schemas.spatial_types import Landmark3D, PersonPose3D, CoordinateSpace
from orbita_human_activity.schemas.tracking_types import TrackState
from orbita_human_activity.tracking.tracker import MultiPersonTracker
from orbita_human_activity.tracking.association import calculate_iou_2d


def make_dummy_pose(x_centroid: float, y_centroid: float, z_centroid: float = 2.0) -> PersonPose3D:
    lms = [
        Landmark3D(index=23, name="LEFT_HIP", x=x_centroid - 0.1, y=y_centroid, z=z_centroid, visibility=0.9, coordinate_space=CoordinateSpace.MEDIAPIPE_WORLD),
        Landmark3D(index=24, name="RIGHT_HIP", x=x_centroid + 0.1, y=y_centroid, z=z_centroid, visibility=0.9, coordinate_space=CoordinateSpace.MEDIAPIPE_WORLD),
    ]
    bbox = (x_centroid - 0.15, y_centroid - 0.5, x_centroid + 0.15, y_centroid + 0.5)
    return PersonPose3D(
        timestamp_ms=0,
        frame_index=0,
        person_id=None,
        world_landmarks=lms,
        bbox_2d=bbox
    )


class TestTrackingAssociation(unittest.TestCase):

    def test_iou_calculation(self):
        b1 = (0.0, 0.0, 1.0, 1.0)
        b2 = (0.0, 0.0, 1.0, 1.0)
        self.assertAlmostEqual(calculate_iou_2d(b1, b2), 1.0)

        b3 = (2.0, 2.0, 3.0, 3.0)
        self.assertAlmostEqual(calculate_iou_2d(b1, b3), 0.0)

    def test_two_person_initialization(self):
        tracker = MultiPersonTracker(max_persons=2)
        p1 = make_dummy_pose(-0.5, 0.0)
        p2 = make_dummy_pose(0.5, 0.0)

        res = tracker.update([p1, p2], timestamp_ms=0)
        self.assertEqual(len(res.active_tracks), 2)
        self.assertIn("HUMAN_1", res.active_tracks)
        self.assertIn("HUMAN_2", res.active_tracks)

    def test_id_persistence_across_movement(self):
        tracker = MultiPersonTracker(max_persons=2)
        p1_f1 = make_dummy_pose(-0.5, 0.0)
        p2_f1 = make_dummy_pose(0.5, 0.0)
        tracker.update([p1_f1, p2_f1], timestamp_ms=0)

        # Frame 2: Slight movement
        p1_f2 = make_dummy_pose(-0.48, 0.0)
        p2_f2 = make_dummy_pose(0.52, 0.0)
        res2 = tracker.update([p1_f2, p2_f2], timestamp_ms=33)

        self.assertEqual(res2.active_tracks["HUMAN_1"].last_centroid_3d[0], -0.48)
        self.assertEqual(res2.active_tracks["HUMAN_2"].last_centroid_3d[0], 0.52)

    def test_temporary_occlusion_coasting(self):
        tracker = MultiPersonTracker(max_persons=2, max_lost_frames=5)
        p1 = make_dummy_pose(-0.5, 0.0)
        tracker.update([p1], timestamp_ms=0)
        tracker.update([p1], timestamp_ms=33) # 2 hits -> CONFIRMED

        # Frame 3: Person 1 is occluded/missing
        res3 = tracker.update([], timestamp_ms=66)
        self.assertIn("HUMAN_1", res3.active_tracks)
        self.assertEqual(res3.active_tracks["HUMAN_1"].state, TrackState.COASTING)
        self.assertEqual(res3.active_tracks["HUMAN_1"].lost_frames, 1)

        # Frame 4: Person 1 re-appears
        res4 = tracker.update([p1], timestamp_ms=100)
        self.assertEqual(res4.active_tracks["HUMAN_1"].state, TrackState.CONFIRMED)
        self.assertEqual(res4.active_tracks["HUMAN_1"].lost_frames, 0)


if __name__ == "__main__":
    unittest.main()
