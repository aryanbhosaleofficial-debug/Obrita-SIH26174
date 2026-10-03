"""Frame-valid 3D Torso Orientation (Roll, Pitch, Yaw) calculation."""

from typing import Optional, Tuple
import numpy as np

from ..schemas.spatial_types import CoordinateSpace, PersonPose3D
from ..schemas.feature_types import OrientationFeatures


class TorsoOrientationEstimator:
    """Computes roll, pitch, and yaw strictly from valid 3D spatial frames.
    
    ENGINEERING RULES & LIMITATIONS:
    1. Raw 2D normalized image coordinates CANNOT determine 3D orientation; attempting
       to do so creates mathematically invalid perspective ambiguities.
    2. Physical roll/pitch/yaw requires either:
       a. MEDIAPIPE_WORLD: 3D hip-centered metric coords (relative to camera line-of-sight).
       b. RACK_RELATIVE_CALIBRATED: 3D metric coords (relative to equipment rack faceplate).
    3. Torso Coordinate Frame Construction:
       - Origin: Midpoint of Left and Right Hips.
       - X_torso (Lateral axis): Vector from Left Shoulder to Right Shoulder.
       - Y_torso (Longitudinal axis): Vector from Mid-Hip to Mid-Shoulder.
       - Z_torso (Sagittal / Normal axis): Normalized cross-product (X_torso × Y_torso) pointing forward.
       - Re-orthonormalized via Gram-Schmidt:
         X_orth = normalize(X_torso)
         Z_orth = normalize(cross(X_orth, Y_torso))
         Y_orth = cross(Z_orth, X_orth)
    4. Euler Angle Extraction (Intrinsic Z-Y-X / Yaw-Pitch-Roll):
       - Pitch: Rotation about lateral axis (tilt forward/backward).
       - Roll: Rotation about sagittal axis (lean left/right).
       - Yaw: Rotation about longitudinal axis (body twist).
    """

    def __init__(self, min_joint_confidence: float = 0.5):
        self.min_confidence = min_joint_confidence

    def compute_orientation(self, pose: PersonPose3D) -> OrientationFeatures:
        """Computes roll, pitch, yaw if 3D coordinates and required torso joints are valid."""
        # 1. Coordinate frame validity check
        active_landmarks = list(pose.landmark_map.values())
        if not active_landmarks:
            return OrientationFeatures(
                is_valid=False,
                reference_frame="NONE",
                warning_note="No 3D spatial landmarks present. Orientation cannot be inferred from 2D coordinates."
            )

        ref_frame_name = active_landmarks[0].coordinate_space

        lms = pose.landmark_map
        ls_lm = lms.get("LEFT_SHOULDER")
        rs_lm = lms.get("RIGHT_SHOULDER")
        lh_lm = lms.get("LEFT_HIP")
        rh_lm = lms.get("RIGHT_HIP")

        for lm, name in [(ls_lm, "LEFT_SHOULDER"), (rs_lm, "RIGHT_SHOULDER"),
                         (lh_lm, "LEFT_HIP"), (rh_lm, "RIGHT_HIP")]:
            if lm is None or not lm.is_confident(self.min_confidence, self.min_confidence):
                return OrientationFeatures(
                    is_valid=False,
                    reference_frame=str(ref_frame_name),
                    warning_note=f"Required torso landmark {name} is occluded or below confidence threshold."
                )

        ls = ls_lm.to_numpy()
        rs = rs_lm.to_numpy()
        lh = lh_lm.to_numpy()
        rh = rh_lm.to_numpy()

        # Anatomical vectors
        mid_shoulders = 0.5 * (ls + rs)
        mid_hips = 0.5 * (lh + rh)

        x_raw = rs - ls                    # Lateral axis
        y_raw = mid_shoulders - mid_hips   # Longitudinal axis

        norm_x = np.linalg.norm(x_raw)
        norm_y = np.linalg.norm(y_raw)
        if norm_x < 1e-4 or norm_y < 1e-4:
            return OrientationFeatures(
                is_valid=False,
                reference_frame=str(ref_frame_name),
                warning_note="Degenerate torso landmarks with zero span."
            )

        # Orthonormal basis
        x_axis = x_raw / norm_x
        z_raw = np.cross(x_axis, y_raw)
        norm_z = np.linalg.norm(z_raw)
        if norm_z < 1e-4:
            return OrientationFeatures(
                is_valid=False,
                reference_frame=str(ref_frame_name),
                warning_note="Collinear torso points; normal vector cannot be resolved."
            )
        z_axis = z_raw / norm_z
        y_axis = np.cross(z_axis, x_axis)

        # Rotation matrix of torso relative to reference frame: columns are [x_axis, y_axis, z_axis]
        R_torso = np.column_stack([x_axis, y_axis, z_axis])

        # Extract Tait-Bryan angles (Z-Y-X: Yaw, Pitch, Roll)
        # sy = sqrt(R[0,0]^2 + R[1,0]^2)
        sy = np.sqrt(R_torso[0, 0] ** 2 + R_torso[1, 0] ** 2)
        singular = sy < 1e-6

        if not singular:
            roll = np.arctan2(R_torso[2, 1], R_torso[2, 2])
            pitch = np.arctan2(-R_torso[2, 0], sy)
            yaw = np.arctan2(R_torso[1, 0], R_torso[0, 0])
        else:
            roll = np.arctan2(-R_torso[1, 2], R_torso[1, 1])
            pitch = np.arctan2(-R_torso[2, 0], sy)
            yaw = 0.0

        return OrientationFeatures(
            roll_deg=float(np.degrees(roll)),
            pitch_deg=float(np.degrees(pitch)),
            yaw_deg=float(np.degrees(yaw)),
            is_valid=True,
            reference_frame=str(ref_frame_name),
            warning_note=None
        )
