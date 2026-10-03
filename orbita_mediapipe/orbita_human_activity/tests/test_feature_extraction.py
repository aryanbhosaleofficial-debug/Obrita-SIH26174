"""Unit tests for kinematic features, frame-valid orientation, and missingness masks."""

import unittest
import numpy as np

from orbita_human_activity.schemas.spatial_types import Landmark3D, PersonPose3D, CoordinateSpace
from orbita_human_activity.features.kinematics import compute_angle_3d, compute_distance_3d
from orbita_human_activity.features.orientation import TorsoOrientationEstimator
from orbita_human_activity.features.temporal_features import TemporalFeatureBuilder


class TestFeatureExtraction(unittest.TestCase):

    @staticmethod
    def _torso_pose(rotation, timestamp_ms=1234, frame_index=17, person_id="HUMAN_1"):
        base = {
            "LEFT_SHOULDER": (-0.2, 0.4, 0.0),
            "RIGHT_SHOULDER": (0.2, 0.4, 0.0),
            "LEFT_HIP": (-0.1, -0.1, 0.0),
            "RIGHT_HIP": (0.1, -0.1, 0.0),
        }
        landmarks = [Landmark3D(
            index=i, name=name, x=float((rotation @ np.array(point))[0]),
            y=float((rotation @ np.array(point))[1]), z=float((rotation @ np.array(point))[2]),
            visibility=0.99, presence=0.99, coordinate_space=CoordinateSpace.MEDIAPIPE_WORLD
        ) for i, (name, point) in enumerate(base.items())]
        return PersonPose3D(
            timestamp_ms=timestamp_ms, frame_index=frame_index, person_id=person_id,
            world_landmarks=landmarks
        )

    def test_orientation_is_finite_at_90_and_180_degree_rotations(self):
        estimator = TorsoOrientationEstimator()
        rotations = [
            np.array([[0, -1, 0], [1, 0, 0], [0, 0, 1]], dtype=float),
            np.array([[-1, 0, 0], [0, -1, 0], [0, 0, 1]], dtype=float),
        ]
        for rotation in rotations:
            result = estimator.compute_orientation(self._torso_pose(rotation))
            self.assertTrue(result.is_valid)
            self.assertTrue(np.all(np.isfinite([
                result.roll_deg, result.pitch_deg, result.yaw_deg
            ])))

    def test_pose_metadata_is_preserved(self):
        pose = self._torso_pose(np.eye(3))
        self.assertEqual((pose.timestamp_ms, pose.frame_index, pose.person_id), (1234, 17, "HUMAN_1"))

    def test_3d_angle_calculation(self):
        # Right angle: A=(0, 1, 0), B=(0, 0, 0), C=(1, 0, 0)
        p_a = np.array([0.0, 1.0, 0.0])
        p_b = np.array([0.0, 0.0, 0.0])
        p_c = np.array([1.0, 0.0, 0.0])
        angle = compute_angle_3d(p_a, p_b, p_c)
        self.assertIsNotNone(angle)
        self.assertAlmostEqual(angle, 90.0, places=4)

        # Straight angle: A=(-1, 0, 0), B=(0, 0, 0), C=(1, 0, 0)
        p_straight = np.array([-1.0, 0.0, 0.0])
        angle_straight = compute_angle_3d(p_straight, p_b, p_c)
        self.assertAlmostEqual(angle_straight, 180.0, places=4)

    def test_3d_distance_calculation(self):
        p_a = np.array([0.0, 0.0, 0.0])
        p_b = np.array([3.0, 4.0, 0.0])
        dist = compute_distance_3d(p_a, p_b)
        self.assertAlmostEqual(dist, 5.0, places=5)

    def test_orientation_rejection_without_3d_landmarks(self):
        """Pure 2D landmarks must be rejected for 3D physical roll/pitch/yaw."""
        norm_lms = [
            Landmark3D(index=11, name="LEFT_SHOULDER", x=0.4, y=0.3, z=0.0, coordinate_space=CoordinateSpace.NORMALIZED_IMAGE),
            Landmark3D(index=12, name="RIGHT_SHOULDER", x=0.6, y=0.3, z=0.0, coordinate_space=CoordinateSpace.NORMALIZED_IMAGE),
            Landmark3D(index=23, name="LEFT_HIP", x=0.4, y=0.7, z=0.0, coordinate_space=CoordinateSpace.NORMALIZED_IMAGE),
            Landmark3D(index=24, name="RIGHT_HIP", x=0.6, y=0.7, z=0.0, coordinate_space=CoordinateSpace.NORMALIZED_IMAGE),
        ]
        pose = PersonPose3D(
            timestamp_ms=0,
            frame_index=0,
            normalized_landmarks=norm_lms,
            world_landmarks=[],  # No 3D landmarks
            rack_relative_landmarks=None
        )
        estimator = TorsoOrientationEstimator()
        orient = estimator.compute_orientation(pose)
        self.assertFalse(orient.is_valid)
        self.assertIn("No 3D spatial landmarks present", orient.warning_note)

    def test_feature_vector_dimension_and_mask(self):
        """Verifies D=74 feature vector and matching missingness mask."""
        world_lms = [
            Landmark3D(index=0, name="NOSE", x=0.0, y=0.6, z=0.0, visibility=0.9, coordinate_space=CoordinateSpace.MEDIAPIPE_WORLD),
            Landmark3D(index=11, name="LEFT_SHOULDER", x=-0.2, y=0.4, z=0.0, visibility=0.9, coordinate_space=CoordinateSpace.MEDIAPIPE_WORLD),
            Landmark3D(index=12, name="RIGHT_SHOULDER", x=0.2, y=0.4, z=0.0, visibility=0.9, coordinate_space=CoordinateSpace.MEDIAPIPE_WORLD),
            Landmark3D(index=13, name="LEFT_ELBOW", x=-0.2, y=0.1, z=0.0, visibility=0.9, coordinate_space=CoordinateSpace.MEDIAPIPE_WORLD),
            Landmark3D(index=14, name="RIGHT_ELBOW", x=0.2, y=0.1, z=0.0, visibility=0.9, coordinate_space=CoordinateSpace.MEDIAPIPE_WORLD),
            Landmark3D(index=15, name="LEFT_WRIST", x=-0.2, y=-0.1, z=0.0, visibility=0.9, coordinate_space=CoordinateSpace.MEDIAPIPE_WORLD),
            Landmark3D(index=16, name="RIGHT_WRIST", x=0.2, y=-0.1, z=0.0, visibility=0.9, coordinate_space=CoordinateSpace.MEDIAPIPE_WORLD),
            Landmark3D(index=23, name="LEFT_HIP", x=-0.1, y=-0.1, z=0.0, visibility=0.9, coordinate_space=CoordinateSpace.MEDIAPIPE_WORLD),
            Landmark3D(index=24, name="RIGHT_HIP", x=0.1, y=-0.1, z=0.0, visibility=0.9, coordinate_space=CoordinateSpace.MEDIAPIPE_WORLD),
            Landmark3D(index=25, name="LEFT_KNEE", x=-0.1, y=-0.5, z=0.0, visibility=0.9, coordinate_space=CoordinateSpace.MEDIAPIPE_WORLD),
            Landmark3D(index=26, name="RIGHT_KNEE", x=0.1, y=-0.5, z=0.0, visibility=0.9, coordinate_space=CoordinateSpace.MEDIAPIPE_WORLD),
            Landmark3D(index=27, name="LEFT_ANKLE", x=-0.1, y=-0.9, z=0.0, visibility=0.9, coordinate_space=CoordinateSpace.MEDIAPIPE_WORLD),
            Landmark3D(index=28, name="RIGHT_ANKLE", x=0.1, y=-0.9, z=0.0, visibility=0.9, coordinate_space=CoordinateSpace.MEDIAPIPE_WORLD),
        ]
        pose = PersonPose3D(
            timestamp_ms=100,
            frame_index=1,
            person_id="HUMAN_1",
            world_landmarks=world_lms
        )
        builder = TemporalFeatureBuilder(sequence_length=30)
        ffv = builder.extract_frame_features(pose)
        self.assertEqual(len(ffv.feature_vector), 74)
        self.assertEqual(len(ffv.missingness_mask), 74)
        # Verify valid values are masked with 1.0
        self.assertGreater(np.sum(ffv.missingness_mask), 30.0)


if __name__ == "__main__":
    unittest.main()
