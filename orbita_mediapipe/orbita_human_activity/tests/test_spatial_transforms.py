"""Unit tests for 3D coordinate transformations and rack calibration."""

import unittest
import numpy as np

from orbita_human_activity.schemas.spatial_types import CoordinateSpace, Landmark3D
from orbita_human_activity.spatial.coordinate_systems import CoordinateFrameManager
from orbita_human_activity.spatial.calibration import RackCalibrationManager


class TestSpatialTransforms(unittest.TestCase):

    def setUp(self):
        self.R = np.eye(3, dtype=np.float32)
        self.T = np.array([0.5, 0.0, 2.0], dtype=np.float32)
        self.frame_mgr = CoordinateFrameManager(
            rotation_matrix=self.R,
            translation_cam_to_rack=self.T,
            is_calibrated=True
        )

    def test_translation_transformation(self):
        """P_rack = R @ (P_cam - T). For R=I, P_rack = P_cam - T."""
        cam_point = np.array([1.5, 1.0, 3.0], dtype=np.float32)
        expected_rack = np.array([1.0, 1.0, 1.0], dtype=np.float32)

        p_rack, is_cal = self.frame_mgr.transform_point_to_rack(cam_point)
        self.assertTrue(is_cal)
        np.testing.assert_allclose(p_rack, expected_rack, atol=1e-5)

    def test_rotation_transformation(self):
        """90 degree rotation about Z axis."""
        # 90 deg rotation around Z
        R_z90 = np.array([
            [0.0, -1.0, 0.0],
            [1.0, 0.0, 0.0],
            [0.0, 0.0, 1.0]
        ], dtype=np.float32)
        mgr = CoordinateFrameManager(rotation_matrix=R_z90, translation_cam_to_rack=np.zeros(3))
        cam_pt = np.array([1.0, 0.0, 0.0], dtype=np.float32)
        p_rack, _ = mgr.transform_point_to_rack(cam_pt)
        # R @ [1, 0, 0] = [0, 1, 0]
        np.testing.assert_allclose(p_rack, np.array([0.0, 1.0, 0.0]), atol=1e-5)

    def test_landmark_list_transformation(self):
        lms = [
            Landmark3D(index=0, name="NOSE", x=0.5, y=0.0, z=2.0, visibility=0.9, coordinate_space=CoordinateSpace.MEDIAPIPE_WORLD)
        ]
        rack_lms = self.frame_mgr.transform_landmarks_to_rack(lms)
        self.assertEqual(len(rack_lms), 1)
        self.assertEqual(rack_lms[0].coordinate_space, CoordinateSpace.RACK_RELATIVE_CALIBRATED)
        self.assertAlmostEqual(rack_lms[0].x, 0.0, places=5)
        self.assertAlmostEqual(rack_lms[0].y, 0.0, places=5)
        self.assertAlmostEqual(rack_lms[0].z, 0.0, places=5)

    def test_unvalidated_transform_is_not_marked_calibrated(self):
        mgr = CoordinateFrameManager(
            rotation_matrix=np.eye(3),
            translation_cam_to_rack=np.zeros(3),
            is_calibrated=False,
        )
        rack_lms = mgr.transform_landmarks_to_rack([
            Landmark3D(index=0, name="NOSE", x=1.0, y=2.0, z=3.0)
        ])
        self.assertEqual(rack_lms[0].coordinate_space, CoordinateSpace.RACK_RELATIVE_UNVALIDATED)

    def test_calibration_rejects_collinear_points(self):
        calibrator = RackCalibrationManager()
        points = np.array([[0, 0, 0], [1, 1, 1], [2, 2, 2]], dtype=np.float32)
        result = calibrator.solve_rigid_transform(points, points)
        self.assertFalse(result.is_valid)
        self.assertIn("Degenerate", result.notes)

    def test_rack_calibration_solver(self):
        calibrator = RackCalibrationManager(max_allowed_rms_error_mm=15.0)

        # Ground truth rack corners
        rack_pts = np.array([
            [0.0, 0.0, 0.0],
            [0.6, 0.0, 0.0],
            [0.6, 1.2, 0.0],
            [0.0, 1.2, 0.0]
        ], dtype=np.float32)

        # Simulated camera points with known offset T = [0.1, 0.2, 1.5]
        true_T = np.array([0.1, 0.2, 1.5], dtype=np.float32)
        cam_pts = rack_pts + true_T

        result = calibrator.solve_rigid_transform(cam_pts, rack_pts)
        self.assertTrue(result.is_valid)
        self.assertLess(result.reprojection_error_rms_mm, 1.0)
        np.testing.assert_allclose(result.translation_vector, true_T, atol=1e-4)


if __name__ == "__main__":
    unittest.main()
