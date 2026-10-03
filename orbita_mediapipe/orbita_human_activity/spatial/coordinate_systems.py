"""Coordinate frame systems and transformations for ORBITA."""

from typing import Dict, List, Optional, Tuple
import numpy as np

from ..schemas.spatial_types import CoordinateSpace, Landmark3D, LANDMARK_NAMES


class CoordinateFrameManager:
    """Manages spatial coordinate frame representations and conversions.
    
    CRITICAL ON-BOARD BAS FLIGHT PRINCIPLES:
    1. Gravity does NOT define 'Up': In orbital microgravity (ISS / BAS module),
       there is no persistent downward acceleration vector. The coordinate frame
       is strictly anchored to the rigid mechanical structure of the experiment rack.
    2. Coordinate Space Distinctions:
       - NORMALIZED_IMAGE: Raw 2D sensor projections + pseudo-depth. No physical metric scale.
       - MEDIAPIPE_WORLD: 3D metric estimation centered at the subject's hips.
         Estimated by the neural network from 2D appearance; subject to model bias and scale drift.
       - RACK_RELATIVE_CALIBRATED: 3D physical coordinates in the certified equipment rack frame,
         achieved via rigid transformation [R | T] with documented optical calibration.
    """

    def __init__(
        self,
        rotation_matrix: Optional[np.ndarray] = None,
        translation_cam_to_rack: Optional[np.ndarray] = None,
        is_calibrated: bool = False
    ):
        """Initialize coordinate manager.
        
        Args:
            rotation_matrix: 3x3 orthonormal rotation matrix from camera to rack frame.
            translation_cam_to_rack: 3D vector [tx, ty, tz] in meters from camera to rack origin.
            is_calibrated: Whether extrinsic parameters have been verified by calibration procedure.
        """
        self.R = rotation_matrix if rotation_matrix is not None else np.eye(3, dtype=np.float32)
        self.T = translation_cam_to_rack if translation_cam_to_rack is not None else np.array([0.0, 0.25, 1.80], dtype=np.float32)
        self.is_calibrated = is_calibrated

    def transform_point_to_rack(self, point_camera_world: np.ndarray) -> Tuple[np.ndarray, bool]:
        """Transform a 3D point in camera-world space to rack-relative space.
        
        Equation: P_rack = R @ (P_cam - T)
        
        Returns:
            Tuple of (transformed_point_3d, is_valid_metric)
        """
        p = np.asarray(point_camera_world, dtype=np.float32)
        if p.shape != (3,):
            raise ValueError(f"Expected 3D point (shape (3,)), got {p.shape}")
            
        p_rack = self.R @ (p - self.T)
        return p_rack, self.is_calibrated

    def transform_landmarks_to_rack(
        self,
        world_landmarks: List[Landmark3D]
    ) -> List[Landmark3D]:
        """Converts a full list of 3D world landmarks into rack-relative landmarks."""
        rack_landmarks = []
        for lm in world_landmarks:
            p_cam = lm.to_numpy()
            p_rack, is_cal = self.transform_point_to_rack(p_cam)
            rack_lm = Landmark3D(
                index=lm.index,
                name=lm.name,
                x=float(p_rack[0]),
                y=float(p_rack[1]),
                z=float(p_rack[2]),
                visibility=lm.visibility,
                presence=lm.presence,
                coordinate_space=(
                    CoordinateSpace.RACK_RELATIVE_CALIBRATED
                    if is_cal
                    else CoordinateSpace.RACK_RELATIVE_UNVALIDATED
                )
            )
            rack_landmarks.append(rack_lm)
        return rack_landmarks
