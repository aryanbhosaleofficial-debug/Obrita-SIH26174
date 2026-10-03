"""Transformation of MediaPipe PoseLandmarker results into ORBITA 3D representations."""

from typing import List, Optional, Tuple, Any
import numpy as np

from ..schemas.spatial_types import (
    CoordinateSpace,
    Landmark3D,
    PersonPose3D,
    LANDMARK_NAMES
)
from .coordinate_systems import CoordinateFrameManager


class PoseLandmarkerAdapter:
    """Adapts raw MediaPipe PoseLandmarker outputs into documented 3D PersonPose3D structures."""

    def __init__(self, frame_manager: Optional[CoordinateFrameManager] = None):
        self.frame_manager = frame_manager or CoordinateFrameManager()

    def process_result(
        self,
        pose_landmarker_result: Any,
        timestamp_ms: int,
        frame_index: int
    ) -> List[PersonPose3D]:
        """Convert a MediaPipe PoseLandmarkerResult into a list of PersonPose3D.
        
        Args:
            pose_landmarker_result: MediaPipe PoseLandmarkerResult instance.
            timestamp_ms: Monotonic frame timestamp in milliseconds.
            frame_index: Sequential integer frame index.
            
        Returns:
            List of PersonPose3D objects (one per detected person).
        """
        if pose_landmarker_result is None:
            return []

        # Access landmarks (normalized image coords) and world landmarks (metric coords)
        normalized_poses = getattr(pose_landmarker_result, 'pose_landmarks', [])
        world_poses = getattr(pose_landmarker_result, 'pose_world_landmarks', [])

        num_persons = max(len(normalized_poses), len(world_poses))
        output_poses: List[PersonPose3D] = []

        for p_idx in range(num_persons):
            norm_lms_raw = normalized_poses[p_idx] if p_idx < len(normalized_poses) else []
            world_lms_raw = world_poses[p_idx] if p_idx < len(world_poses) else []

            # 1. Parse Normalized Landmarks
            parsed_norm_lms: List[Landmark3D] = []
            x_vals_norm, y_vals_norm = [], []
            for idx, lm in enumerate(norm_lms_raw):
                name = LANDMARK_NAMES[idx] if idx < len(LANDMARK_NAMES) else f"LANDMARK_{idx}"
                x = getattr(lm, 'x', 0.0)
                y = getattr(lm, 'y', 0.0)
                z = getattr(lm, 'z', 0.0)
                vis = getattr(lm, 'visibility', None)
                pres = getattr(lm, 'presence', None)
                
                parsed_norm_lms.append(Landmark3D(
                    index=idx,
                    name=name,
                    x=float(x),
                    y=float(y),
                    z=float(z),
                    visibility=float(vis) if vis is not None else None,
                    presence=float(pres) if pres is not None else None,
                    coordinate_space=CoordinateSpace.NORMALIZED_IMAGE
                ))
                x_vals_norm.append(x)
                y_vals_norm.append(y)

            # 2D Bounding box calculation [xmin, ymin, xmax, ymax]
            bbox_2d = None
            if x_vals_norm and y_vals_norm:
                bbox_2d = (
                    float(min(x_vals_norm)),
                    float(min(y_vals_norm)),
                    float(max(x_vals_norm)),
                    float(max(y_vals_norm))
                )

            # 2. Parse World Landmarks
            parsed_world_lms: List[Landmark3D] = []
            for idx, lm in enumerate(world_lms_raw):
                name = LANDMARK_NAMES[idx] if idx < len(LANDMARK_NAMES) else f"LANDMARK_{idx}"
                x = getattr(lm, 'x', 0.0)
                y = getattr(lm, 'y', 0.0)
                z = getattr(lm, 'z', 0.0)
                vis = getattr(lm, 'visibility', None)
                pres = getattr(lm, 'presence', None)
                
                parsed_world_lms.append(Landmark3D(
                    index=idx,
                    name=name,
                    x=float(x),
                    y=float(y),
                    z=float(z),
                    visibility=float(vis) if vis is not None else None,
                    presence=float(pres) if pres is not None else None,
                    coordinate_space=CoordinateSpace.MEDIAPIPE_WORLD
                ))

            # 3. Transform to Rack-Relative coordinates if frame_manager is configured
            rack_lms = None
            if parsed_world_lms:
                rack_lms = self.frame_manager.transform_landmarks_to_rack(parsed_world_lms)

            pose_3d = PersonPose3D(
                timestamp_ms=timestamp_ms,
                frame_index=frame_index,
                person_id=None,  # Will be assigned by Tracker
                normalized_landmarks=parsed_norm_lms,
                world_landmarks=parsed_world_lms,
                rack_relative_landmarks=rack_lms,
                bbox_2d=bbox_2d,
                is_tracked=False
            )
            output_poses.append(pose_3d)

        return output_poses
