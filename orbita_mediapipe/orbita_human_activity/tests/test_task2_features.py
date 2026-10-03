"""Focused Task 2 tests for deterministic 3D feature/data conversion."""

import json
import os
import tempfile
import unittest

import numpy as np

from orbita_human_activity.features.kinematics import (
    compute_acceleration_3d,
    compute_angle_3d,
    compute_displacement_3d,
    compute_distance_3d,
    compute_unit_vector_3d,
    compute_velocity_3d,
)
from orbita_human_activity.features.temporal_features import TemporalFeatureBuilder, TemporalSequenceManager
from orbita_human_activity.pipeline.serialization import DataLogger
from orbita_human_activity.schemas.feature_types import FrameFeatureVector
from orbita_human_activity.schemas.spatial_types import CoordinateSpace, Landmark3D, PersonPose3D
from orbita_human_activity.training.dataset import OrbitaActivityDataset


class TestTask2Features(unittest.TestCase):
    def make_pose(self, person_id="HUMAN_1", timestamp_ms=0, frame_index=0, wrist_x=0.0, missing=False):
        points = {
            "NOSE": (0.0, 0.6, 0.0), "LEFT_SHOULDER": (-0.2, 0.4, 0.0),
            "RIGHT_SHOULDER": (0.2, 0.4, 0.0), "LEFT_ELBOW": (-0.2, 0.1, 0.0),
            "RIGHT_ELBOW": (0.2, 0.1, 0.0), "LEFT_WRIST": (-0.2 + wrist_x, -0.1, 0.0),
            "RIGHT_WRIST": (0.2, -0.1, 0.0), "LEFT_HIP": (-0.1, -0.1, 0.0),
            "RIGHT_HIP": (0.1, -0.1, 0.0), "LEFT_KNEE": (-0.1, -0.5, 0.0),
            "RIGHT_KNEE": (0.1, -0.5, 0.0), "LEFT_ANKLE": (-0.1, -0.9, 0.0),
            "RIGHT_ANKLE": (0.1, -0.9, 0.0),
        }
        if missing:
            points.pop("LEFT_WRIST")
        landmarks = [Landmark3D(i, name, *point, visibility=0.95, presence=0.95,
                                coordinate_space=CoordinateSpace.MEDIAPIPE_WORLD)
                     for i, (name, point) in enumerate(points.items())]
        return PersonPose3D(timestamp_ms, frame_index, person_id=person_id, world_landmarks=landmarks)

    def test_geometry_utilities(self):
        a, b = np.array([0., 0., 0.]), np.array([1., 0., 0.])
        self.assertAlmostEqual(compute_distance_3d(a, b), 1.0)
        self.assertAlmostEqual(compute_angle_3d(np.array([0., 1., 0.]), a, b), 90.0)
        unit, magnitude = compute_unit_vector_3d(a, b)
        self.assertEqual(unit, [1.0, 0.0, 0.0])
        self.assertAlmostEqual(magnitude, 1.0)

    def test_displacement_velocity_acceleration_use_timestamps(self):
        displacement = compute_displacement_3d(np.array([0., 0., 0.]), np.array([1., 0., 0.]))
        velocity = compute_velocity_3d(np.array([0., 0., 0.]), np.array([1., 0., 0.]), 0.5)
        acceleration = compute_acceleration_3d(np.array([1., 0., 0.]), np.array([3., 0., 0.]), 0.5)
        np.testing.assert_allclose(displacement, [1., 0., 0.])
        np.testing.assert_allclose(velocity, [2., 0., 0.])
        np.testing.assert_allclose(acceleration, [4., 0., 0.])
        self.assertIsNone(compute_velocity_3d(np.zeros(3), np.ones(3), 0.0))

    def test_temporal_metadata_and_person_isolation(self):
        builder = TemporalFeatureBuilder()
        first = builder.extract_frame_features(self.make_pose(timestamp_ms=100, frame_index=1))
        second = builder.extract_frame_features(self.make_pose(timestamp_ms=200, frame_index=2, wrist_x=0.1))
        other = builder.extract_frame_features(self.make_pose("HUMAN_2", timestamp_ms=200, frame_index=2, wrist_x=0.1))
        self.assertEqual(first.coordinate_space, CoordinateSpace.MEDIAPIPE_WORLD.value)
        self.assertEqual(first.human_label, "HUMAN_1")
        self.assertEqual(second.temporal_delta_ms, 100)
        self.assertIn("LEFT_WRIST", second.displacements)
        self.assertIn("LEFT_WRIST", second.velocities)
        self.assertEqual(other.temporal_delta_ms, None)
        self.assertEqual(len(second.feature_vector), 74)

    def test_feature_generation_is_deterministic(self):
        pose = self.make_pose(timestamp_ms=100, frame_index=1)
        first = TemporalFeatureBuilder().extract_frame_features(pose)
        second = TemporalFeatureBuilder().extract_frame_features(self.make_pose(timestamp_ms=100, frame_index=1))
        np.testing.assert_array_equal(first.feature_vector, second.feature_vector)
        np.testing.assert_array_equal(first.missingness_mask, second.missingness_mask)
        self.assertEqual(first.to_dict(), second.to_dict())

    def test_missingness_and_invalid_timestamp_are_explicit(self):
        builder = TemporalFeatureBuilder()
        missing = builder.extract_frame_features(self.make_pose(missing=True))
        self.assertEqual(missing.measurement_status, "VALID_3D")
        self.assertNotIn("LEFT_FOREARM_DIR", missing.kinematic_features["relative_unit_vectors"])
        self.assertLess(np.sum(missing.missingness_mask), 74)
        invalid = builder.extract_frame_features(self.make_pose(timestamp_ms=-1, frame_index=1))
        self.assertEqual(invalid.measurement_status, "INVALID_TIMESTAMP_ORDER")
        self.assertEqual(invalid.velocities, {})

    def test_sequence_order_and_human_isolation(self):
        manager = TemporalSequenceManager(sequence_length=3, step_size=1)
        samples = []
        for i, timestamp in enumerate([0, 10, 20]):
            samples.append(manager.add_frame_feature(
                FrameFeatureVector(timestamp, i, "HUMAN_1", np.zeros(2, dtype=np.float32),
                                   np.ones(2, dtype=np.float32), 1.0,
                                   coordinate_space="MEDIAPIPE_WORLD", human_label="HUMAN_1")
            ))
        self.assertIsNotNone(samples[-1])
        self.assertEqual(samples[-1].person_id, "HUMAN_1")
        self.assertEqual(samples[-1].timestamps_ms, [0, 10, 20])
        self.assertIsNone(manager.add_frame_feature(
            FrameFeatureVector(20, 99, "HUMAN_1", np.zeros(2, dtype=np.float32),
                               np.ones(2, dtype=np.float32), 1.0)
        ))
        other = manager.add_frame_feature(
            FrameFeatureVector(0, 0, "HUMAN_2", np.zeros(2, dtype=np.float32),
                               np.ones(2, dtype=np.float32), 1.0, human_label="HUMAN_2")
        )
        self.assertIsNone(other)

    def test_jsonl_metadata_csv_and_structured_loader(self):
        with tempfile.TemporaryDirectory() as directory:
            logger = DataLogger(directory, "TASK2")
            builder = TemporalFeatureBuilder()
            for i in range(3):
                logger.log_frame_feature(builder.extract_frame_features(
                    self.make_pose(timestamp_ms=i * 10, frame_index=i)))
            dataset = OrbitaActivityDataset.from_feature_jsonl(
                logger.features_jsonl_path, sequence_length=3, step_size=1)
            self.assertEqual(len(dataset), 1)
            x, mask, y = dataset[0]
            self.assertEqual(tuple(x.shape), (3, 74))
            self.assertEqual(tuple(mask.shape), (3, 74))
            self.assertEqual(int(y), 0)
            with open(logger.features_jsonl_path, encoding="utf-8") as handle:
                record = json.loads(handle.readline())
            self.assertIn("feature_schema_version", record)
            self.assertIn("coordinate_space", record)
            self.assertTrue(os.path.exists(logger.features_csv_path))


if __name__ == "__main__":
    unittest.main()
