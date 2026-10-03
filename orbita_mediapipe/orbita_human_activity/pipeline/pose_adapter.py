"""MediaPipe Pose Landmarker runner and synthetic offline generator."""

import os
from pathlib import Path
from typing import Any, List, Optional
import numpy as np

from ..schemas.spatial_types import (
    CoordinateSpace,
    Landmark3D,
    PersonPose3D,
    LANDMARK_NAMES
)
from ..spatial.transforms import PoseLandmarkerAdapter


class MediaPipePoseLandmarkerRunner:
    """Wrapper around MediaPipe PoseLandmarker configured for up to 2 persons."""

    def __init__(
        self,
        model_asset_path: str = "models/pose_landmarker.task",
        num_poses: int = 2,
        min_detection_confidence: float = 0.5,
        min_tracking_confidence: float = 0.5,
        use_synthetic_fallback: bool = True
    ):
        self.model_path = self.resolve_model_asset_path(model_asset_path)
        self.num_poses = num_poses
        self.min_det_conf = min_detection_confidence
        self.min_track_conf = min_tracking_confidence
        self.use_fallback = use_synthetic_fallback
        self.detector = None
        self.is_real_detector = False
        self.adapter = PoseLandmarkerAdapter()

        self._init_detector()

    @staticmethod
    def resolve_model_asset_path(model_asset_path: str) -> str:
        """Resolve configured assets, including the repository-local Heavy bundle."""
        configured = Path(model_asset_path)
        repo_root = Path(__file__).resolve().parents[2]
        candidates = [configured]
        if not configured.is_absolute():
            candidates.append(repo_root / configured)
        if model_asset_path == "models/pose_landmarker.task":
            candidates.append(repo_root / "mediapipe" / "models" / "pose_landmarker_heavy.task")

        for candidate in candidates:
            if candidate.is_file():
                return str(candidate.resolve())
        return model_asset_path

    def _init_detector(self):
        """Attempts to initialize MediaPipe PoseLandmarker if asset exists."""
        if os.path.exists(self.model_path):
            try:
                import mediapipe as mp
                from mediapipe.tasks import python as mp_python
                from mediapipe.tasks.python import vision as mp_vision

                base_options = mp_python.BaseOptions(model_asset_path=self.model_path)
                options = mp_vision.PoseLandmarkerOptions(
                    base_options=base_options,
                    running_mode=mp_vision.RunningMode.IMAGE,
                    num_poses=self.num_poses,
                    min_pose_detection_confidence=self.min_det_conf,
                    min_tracking_confidence=self.min_track_conf,
                    output_segmentation_masks=False
                )
                self.detector = mp_vision.PoseLandmarker.create_from_options(options)
                self.is_real_detector = True
                print(f"[ORBITA] Successfully loaded MediaPipe Pose Landmarker from: {self.model_path}")
                return
            except Exception as e:
                print(f"[ORBITA] Could not initialize native MediaPipe PoseLandmarker ({e}).")

        if self.use_fallback:
            print(f"[ORBITA] Model asset '{self.model_path}' not found or uninitialized.")
            print("[ORBITA] Active mode: Synthetic/Offline Pose Generator for test execution.")
            self.detector = None
            self.is_real_detector = False

    def detect_frame(
        self,
        image_rgb: Optional[np.ndarray],
        timestamp_ms: int,
        frame_index: int
    ) -> List[PersonPose3D]:
        """Detects poses in an image frame or generates synthetic test poses if offline."""
        if self.is_real_detector and self.detector is not None and image_rgb is not None:
            import mediapipe as mp
            mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=image_rgb)
            result = self.detector.detect(mp_image)
            return self.adapter.process_result(result, timestamp_ms, frame_index)

        # Synthetic generator for offline testing
        return self._generate_synthetic_poses(timestamp_ms, frame_index)

    def _generate_synthetic_poses(
        self,
        timestamp_ms: int,
        frame_index: int
    ) -> List[PersonPose3D]:
        """Generates realistic test poses for 2 humans moving in space (e.g. crossing)."""
        poses = []
        t = frame_index * 0.05

        for p_idx, base_x in enumerate([-0.4, 0.4]):
            # Simulate slight swaying and hand motion
            sway_x = base_x + 0.1 * np.sin(t + p_idx * np.pi)
            norm_lms = []
            world_lms = []

            for idx, name in enumerate(LANDMARK_NAMES):
                # Standard standing/floating template
                if "LEFT" in name:
                    x_off = -0.2
                elif "RIGHT" in name:
                    x_off = 0.2
                else:
                    x_off = 0.0

                if "SHOULDER" in name:
                    y_off, z_off = 0.4, 0.0
                elif "ELBOW" in name:
                    y_off, z_off = 0.1, 0.1 * np.sin(t + idx)
                elif "WRIST" in name:
                    y_off, z_off = -0.1 + 0.15 * np.cos(t + idx), 0.25
                elif "HIP" in name:
                    y_off, z_off = -0.1, 0.0
                elif "KNEE" in name:
                    y_off, z_off = -0.5, 0.05
                elif "ANKLE" in name or "FOOT" in name:
                    y_off, z_off = -0.85, 0.1
                else:
                    y_off, z_off = 0.6, 0.0

                # World coordinates (meters, hip-centered)
                wx = float(x_off + 0.05 * np.sin(t))
                wy = float(y_off)
                wz = float(z_off)
                world_lms.append(Landmark3D(
                    index=idx, name=name, x=wx, y=wy, z=wz,
                    visibility=0.95, presence=0.95,
                    coordinate_space=CoordinateSpace.MEDIAPIPE_WORLD
                ))

                # Normalized image coordinates [0, 1]
                nx = float(np.clip(0.5 + sway_x + 0.3 * wx, 0.0, 1.0))
                ny = float(np.clip(0.5 - 0.4 * wy, 0.0, 1.0))
                nz = float(wz)
                norm_lms.append(Landmark3D(
                    index=idx, name=name, x=nx, y=ny, z=nz,
                    visibility=0.95, presence=0.95,
                    coordinate_space=CoordinateSpace.NORMALIZED_IMAGE
                ))

            # Transform to rack-relative
            rack_lms = self.adapter.frame_manager.transform_landmarks_to_rack(world_lms)

            # Bounding box
            xs = [lm.x for lm in norm_lms]
            ys = [lm.y for lm in norm_lms]
            bbox = (min(xs), min(ys), max(xs), max(ys))

            pose = PersonPose3D(
                timestamp_ms=timestamp_ms,
                frame_index=frame_index,
                person_id=None,
                normalized_landmarks=norm_lms,
                world_landmarks=world_lms,
                rack_relative_landmarks=rack_lms,
                bbox_2d=bbox,
                is_tracked=False
            )
            poses.append(pose)

        return poses
