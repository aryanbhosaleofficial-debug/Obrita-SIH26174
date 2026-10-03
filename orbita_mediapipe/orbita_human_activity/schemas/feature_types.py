"""Feature extraction schemas and representation containers."""

from dataclasses import dataclass, field
from typing import Dict, List, Optional
import numpy as np


FEATURE_SCHEMA_VERSION = "2.0.0"


@dataclass
class KinematicFeatures:
    """Documented geometric and kinematic joint features."""
    # Joint Angles (in degrees [0, 180]): e.g., Left/Right Elbow, Left/Right Shoulder, Left/Right Knee
    joint_angles: Dict[str, float] = field(default_factory=dict)
    
    # Inter-joint Euclidean Distances (meters in 3D): e.g., Wrist-to-Wrist, Wrist-to-Shoulder
    joint_distances: Dict[str, float] = field(default_factory=dict)
    
    # Relative Joint Vectors (unit vectors [dx, dy, dz]): e.g., Elbow->Wrist, Shoulder->Elbow
    relative_vectors: Dict[str, List[float]] = field(default_factory=dict)


@dataclass
class OrientationFeatures:
    """Anatomical Torso orientation in degrees (Roll, Pitch, Yaw).
    
    IMPORTANT REASONING / LIMITATIONS:
    - Orientation is computed ONLY when true 3D spatial coordinates (MediaPipe World
      or Rack-Relative) are provided.
    - It is computed relative to the anatomical Torso Reference Frame:
      * Lateral axis (X_torso): Left Shoulder -> Right Shoulder.
      * Longitudinal axis (Y_torso): Midpoint of Hips -> Midpoint of Shoulders.
      * Normal/Sagittal axis (Z_torso): Cross product (X_torso x Y_torso) pointing anteriorly.
    - In microgravity, this measures body attitude relative to the camera/rack, NOT gravity pitch/roll!
    """
    roll_deg: Optional[float] = None
    pitch_deg: Optional[float] = None
    yaw_deg: Optional[float] = None
    is_valid: bool = False
    reference_frame: str = "TORSO_ANATOMICAL_3D"
    warning_note: Optional[str] = None


@dataclass
class FrameFeatureVector:
    """Consolidated 1D numerical feature vector for one person at one time step."""
    timestamp_ms: int
    frame_index: int
    person_id: str
    feature_vector: np.ndarray      # Shape: (D,) float32
    missingness_mask: np.ndarray    # Shape: (D,) float32: 1.0 = valid measurement, 0.0 = missing/occluded
    confidence_score: float         # Aggregate confidence across key joints [0.0, 1.0]
    feature_names: List[str] = field(default_factory=list)
    coordinate_space: str = "UNKNOWN"
    measurement_status: str = "UNKNOWN"
    orientation_status: str = "UNKNOWN"
    human_label: Optional[str] = None
    temporal_delta_ms: Optional[int] = None
    displacements: Dict[str, List[float]] = field(default_factory=dict)
    velocities: Dict[str, List[float]] = field(default_factory=dict)
    accelerations: Dict[str, List[float]] = field(default_factory=dict)
    kinematic_features: Dict[str, Dict] = field(default_factory=dict)

    @property
    def frame_id(self) -> int:
        """Stable frame identifier retained alongside the legacy frame_index name."""
        return self.frame_index

    def to_dict(self) -> Dict:
        """Structured dictionary suitable for JSON serialization."""
        return {
            "feature_schema_version": FEATURE_SCHEMA_VERSION,
            "timestamp_ms": self.timestamp_ms,
            "frame_id": self.frame_id,
            "frame_index": self.frame_index,
            "person_id": self.person_id,
            "human_label": self.human_label,
            "coordinate_space": self.coordinate_space,
            "measurement_status": self.measurement_status,
            "orientation_status": self.orientation_status,
            "temporal_delta_ms": self.temporal_delta_ms,
            "confidence_score": round(float(self.confidence_score), 4),
            "feature_dim": int(len(self.feature_vector)),
            "features": [round(float(v), 5) for v in self.feature_vector],
            "missingness_mask": [int(m) for m in self.missingness_mask],
            "displacements": self.displacements,
            "velocities": self.velocities,
            "accelerations": self.accelerations,
            "kinematic_features": self.kinematic_features,
        }
