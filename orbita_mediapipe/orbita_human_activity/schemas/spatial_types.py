"""3D Spatial Landmark Schemas for ORBITA."""

from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional, Tuple
import numpy as np


class CoordinateSpace(str, Enum):
    """Explicitly distinguished coordinate reference frames.
    
    1. NORMALIZED_IMAGE:
       - Range: [0.0, 1.0] for X and Y, relative to image width/height.
       - Z represents landmark depth relative to hips in normalized image units.
    
    2. MEDIAPIPE_WORLD:
       - Metric scale (~meters).
       - Origin located at the geometric center of the subject's hips.
       - Subject/Camera-aligned axis: X points right, Y points down/feet-ward, Z points forward.
       - NOTE: This is a model-estimated relative coordinate system, NOT an absolute physical reference.
    
    3. RACK_RELATIVE_CALIBRATED:
       - Metric scale (meters).
       - Origin anchored to a verified equipment rack origin [X_rack=0, Y_rack=0, Z_rack=0].
       - Requires rigid body extrinsic transformation [R | T] with documented calibration.
       - Independent of gravity vectors (nominal in microgravity / on-board spacecraft).
    """
    NORMALIZED_IMAGE = "NORMALIZED_IMAGE"
    MEDIAPIPE_WORLD = "MEDIAPIPE_WORLD"
    RACK_RELATIVE_CALIBRATED = "RACK_RELATIVE_CALIBRATED"
    RACK_RELATIVE_UNVALIDATED = "RACK_RELATIVE_UNVALIDATED"


# Canonical MediaPipe 33 Landmark Names
LANDMARK_NAMES = [
    "NOSE", "LEFT_EYE_INNER", "LEFT_EYE", "LEFT_EYE_OUTER",
    "RIGHT_EYE_INNER", "RIGHT_EYE", "RIGHT_EYE_OUTER",
    "LEFT_EAR", "RIGHT_EAR", "MOUTH_LEFT", "MOUTH_RIGHT",
    "LEFT_SHOULDER", "RIGHT_SHOULDER", "LEFT_ELBOW", "RIGHT_ELBOW",
    "LEFT_WRIST", "RIGHT_WRIST", "LEFT_PINKY", "RIGHT_PINKY",
    "LEFT_INDEX", "RIGHT_INDEX", "LEFT_THUMB", "RIGHT_THUMB",
    "LEFT_HIP", "RIGHT_HIP", "LEFT_KNEE", "RIGHT_KNEE",
    "LEFT_ANKLE", "RIGHT_ANKLE", "LEFT_HEEL", "RIGHT_HEEL",
    "LEFT_FOOT_INDEX", "RIGHT_FOOT_INDEX"
]


@dataclass
class Landmark3D:
    """Documented 3D spatial representation of a single anatomical landmark."""
    index: int
    name: str
    x: float
    y: float
    z: float
    visibility: Optional[float] = None
    presence: Optional[float] = None
    coordinate_space: CoordinateSpace = CoordinateSpace.MEDIAPIPE_WORLD

    def to_numpy(self) -> np.ndarray:
        return np.array([self.x, self.y, self.z], dtype=np.float32)

    def is_confident(self, min_visibility: float = 0.5, min_presence: float = 0.5) -> bool:
        v_ok = (self.visibility is None) or (self.visibility >= min_visibility)
        p_ok = (self.presence is None) or (self.presence >= min_presence)
        return v_ok and p_ok


@dataclass
class PersonPose3D:
    """Complete 3D spatial pose snapshot for one person at a single time step."""
    timestamp_ms: int
    frame_index: int
    person_id: Optional[str] = None  # Tracking slot, e.g. "HUMAN_1", "HUMAN_2", or unassigned
    normalized_landmarks: List[Landmark3D] = field(default_factory=list)
    world_landmarks: List[Landmark3D] = field(default_factory=list)
    rack_relative_landmarks: Optional[List[Landmark3D]] = None
    bbox_2d: Optional[Tuple[float, float, float, float]] = None  # (xmin, ymin, xmax, ymax) in [0, 1]
    is_tracked: bool = False
    
    @property
    def landmark_map(self) -> Dict[str, Landmark3D]:
        """Map of landmark name to the active, physically qualified 3D frame.

        Unvalidated rack-relative transforms remain available through
        ``rack_relative_landmarks`` but must not silently replace MediaPipe World
        coordinates as the active physical frame.
        """
        active = self.world_landmarks
        if self.rack_relative_landmarks and all(
            lm.coordinate_space == CoordinateSpace.RACK_RELATIVE_CALIBRATED
            for lm in self.rack_relative_landmarks
        ):
            active = self.rack_relative_landmarks
        return {lm.name: lm for lm in active}

    def get_joint_coords(self, name: str) -> Optional[np.ndarray]:
        lms = list(self.landmark_map.values())
        for lm in lms:
            if lm.name == name:
                return lm.to_numpy()
        return None
