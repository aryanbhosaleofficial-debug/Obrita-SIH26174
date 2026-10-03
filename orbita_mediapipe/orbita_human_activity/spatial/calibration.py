"""Documented Camera-to-Equipment-Rack Calibration Procedure for ORBITA."""

from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple
import numpy as np


@dataclass
class CalibrationResult:
    """Outcome of optical calibration between camera frame and rack frame."""
    is_valid: bool
    reprojection_error_rms_mm: float
    rotation_matrix: np.ndarray
    translation_vector: np.ndarray
    num_calibration_points: int
    notes: str


class RackCalibrationManager:
    """Performs and validates camera-to-rack spatial calibration.
    
    DOCUMENTED CALIBRATION PROTOCOL (Task 1 Requirement):
    -----------------------------------------------------
    1. Problem: MediaPipe World landmarks estimate 3D human pose relative to the
       subject's hip center in camera-aligned axes. They have NO knowledge of
       where the physical experiment rack is situated.
    2. Procedure:
       a. Mount 4 known coplanar fiducials (or ChArUco target) on the rack faceplate:
          - Point 0: Top-Left (0.0, 0.0, 0.0) [Rack Origin]
          - Point 1: Top-Right (0.60, 0.0, 0.0)
          - Point 2: Bottom-Right (0.60, 1.20, 0.0)
          - Point 3: Bottom-Left (0.0, 1.20, 0.0)
       b. Detect 2D / 3D camera coordinates of these fiducials.
       c. Compute optimal rigid transformation [R | T] using Kabsch-Umeyama (SVD) algorithm.
       d. Calculate Root Mean Square (RMS) residual alignment error.
       e. Gate: Require RMS error < 15.0 mm.
    3. Failure Mode: If uncalibrated, rack-relative accuracy CANNOT be claimed.
       The system operates in nominal mode with an explicit unvalidated flag.
    """

    def __init__(self, max_allowed_rms_error_mm: float = 15.0):
        self.max_rms = max_allowed_rms_error_mm

    def solve_rigid_transform(
        self,
        camera_points: np.ndarray,
        rack_points: np.ndarray
    ) -> CalibrationResult:
        """Solves for R and T such that P_rack ≈ R @ (P_cam - T) using SVD.
        
        Args:
            camera_points: (N, 3) coordinates in camera reference frame.
            rack_points: (N, 3) ground truth coordinates on rack faceplate.
        """
        camera_points = np.asarray(camera_points, dtype=np.float64)
        rack_points = np.asarray(rack_points, dtype=np.float64)
        if camera_points.ndim != 2 or rack_points.ndim != 2 or camera_points.shape != rack_points.shape:
            raise ValueError("camera_points and rack_points must both have shape (N, 3)")
        if camera_points.shape[1] != 3:
            raise ValueError("camera_points and rack_points must both have shape (N, 3)")
        N = camera_points.shape[0]
        if N < 3:
            return CalibrationResult(
                is_valid=False,
                reprojection_error_rms_mm=float('inf'),
                rotation_matrix=np.eye(3),
                translation_vector=np.zeros(3),
                num_calibration_points=N,
                notes="Insufficient points (minimum 3 non-collinear points required)."
            )

        # Centroids
        cam_centroid = np.mean(camera_points, axis=0)
        rack_centroid = np.mean(rack_points, axis=0)

        # Centered coordinates
        cam_centered = camera_points - cam_centroid
        rack_centered = rack_points - rack_centroid

        # A rigid 3D frame cannot be established from collinear points.
        if np.linalg.matrix_rank(camera_points - np.mean(camera_points, axis=0)) < 2 or \
                np.linalg.matrix_rank(rack_points - np.mean(rack_points, axis=0)) < 2:
            return CalibrationResult(
                is_valid=False,
                reprojection_error_rms_mm=float('inf'),
                rotation_matrix=np.eye(3),
                translation_vector=np.zeros(3),
                num_calibration_points=N,
                notes="Degenerate calibration geometry (points must span a plane or volume)."
            )

        # Covariance matrix H
        H = cam_centered.T @ rack_centered

        # SVD
        U, S, Vt = np.linalg.svd(H)
        R = Vt.T @ U.T

        # Ensure right-handed coordinate system (det(R) == +1)
        if np.linalg.det(R) < 0:
            Vt[2, :] *= -1
            R = Vt.T @ U.T

        # Translation: rack_centroid = R @ (cam_centroid - T) => T = cam_centroid - R.T @ rack_centroid
        T = cam_centroid - (R.T @ rack_centroid)

        # Compute RMS error
        projected_rack = (R @ (camera_points - T).T).T
        residuals = projected_rack - rack_points
        rms_error_m = np.sqrt(np.mean(np.sum(residuals**2, axis=1)))
        rms_error_mm = float(rms_error_m * 1000.0)

        is_valid = rms_error_mm <= self.max_rms
        notes = (
            f"Calibration verified: RMS error = {rms_error_mm:.2f} mm (< {self.max_rms} mm)"
            if is_valid
            else f"Calibration REJECTED: RMS error {rms_error_mm:.2f} mm exceeds tolerance {self.max_rms} mm"
        )

        return CalibrationResult(
            is_valid=is_valid,
            reprojection_error_rms_mm=rms_error_mm,
            rotation_matrix=R,
            translation_vector=T,
            num_calibration_points=N,
            notes=notes
        )
