"""Temporal feature extraction, velocity calculation, and sequence windowing."""

from typing import Dict, List, Optional, Tuple
import numpy as np

from ..schemas.spatial_types import PersonPose3D
from ..schemas.feature_types import (
    FEATURE_SCHEMA_VERSION,
    KinematicFeatures,
    OrientationFeatures,
    FrameFeatureVector
)
from ..schemas.dataset_types import TemporalSequenceSample
from .kinematics import KinematicExtractor, compute_acceleration_3d, compute_displacement_3d, compute_velocity_3d
from .orientation import TorsoOrientationEstimator


# Key functional landmarks for HAR representation
CORE_LANDMARKS = [
    "NOSE", "LEFT_SHOULDER", "RIGHT_SHOULDER",
    "LEFT_ELBOW", "RIGHT_ELBOW", "LEFT_WRIST", "RIGHT_WRIST",
    "LEFT_HIP", "RIGHT_HIP", "LEFT_KNEE", "RIGHT_KNEE",
    "LEFT_ANKLE", "RIGHT_ANKLE"
]


class TemporalFeatureBuilder:
    """Builds numerical feature vectors with temporal differences and sliding sequence buffers."""

    def __init__(
        self,
        sequence_length: int = 30,
        min_confidence: float = 0.5
    ):
        self.sequence_length = sequence_length
        self.min_confidence = min_confidence
        self.kin_extractor = KinematicExtractor(min_confidence=min_confidence)
        self.orient_estimator = TorsoOrientationEstimator(min_joint_confidence=min_confidence)
        
        # Per-person state history: person_id -> list of (timestamp_ms, coords_dict)
        self.history: Dict[str, List[Tuple[int, Dict[str, np.ndarray], Dict[str, np.ndarray]]]] = {}

    def extract_frame_features(
        self,
        pose: PersonPose3D
    ) -> FrameFeatureVector:
        """Constructs a consolidated numerical feature vector and explicit missingness mask.
        
        Total Feature Vector Composition (D = 74 dimensions):
        - 13 Key 3D Joint Positions (x, y, z): 13 * 3 = 39 dims
        - 13 Key 3D Joint Velocities (dx/dt, dy/dt, dz/dt): 13 * 3 = 39 dims -> we use 6 key functional upper/lower: 6 * 3 = 18 dims
        - 6 Joint Angles: 6 dims
        - 5 Key Distances: 5 dims
        - 3 Torso Orientation angles (Roll, Pitch, Yaw): 3 dims
        - 3 Torso centroid velocity: 3 dims
        Total: 39 + 18 + 6 + 5 + 3 + 3 = 74 dimensions.
        """
        person_id = pose.person_id or "UNTRACKED"
        timestamp_ms = pose.timestamp_ms
        frame_idx = pose.frame_index
        lms = pose.landmark_map

        features: List[float] = []
        mask: List[float] = []
        feature_names: List[str] = []
        confidences: List[float] = []

        curr_coords: Dict[str, np.ndarray] = {}

        # 1. Core 3D Joint Positions (39 dims)
        for lm_name in CORE_LANDMARKS:
            lm = lms.get(lm_name)
            is_valid = (lm is not None) and lm.is_confident(self.min_confidence, self.min_confidence)
            if is_valid and lm is not None:
                curr_coords[lm_name] = lm.to_numpy()
                pos = lm.to_numpy()
                features.extend([float(pos[0]), float(pos[1]), float(pos[2])])
                mask.extend([1.0, 1.0, 1.0])
                if lm.visibility is not None:
                    confidences.append(lm.visibility)
            else:
                features.extend([0.0, 0.0, 0.0])
                mask.extend([0.0, 0.0, 0.0])
                confidences.append(0.0)
            feature_names.extend([f"{lm_name}_X", f"{lm_name}_Y", f"{lm_name}_Z"])

        # 2. Key Velocities (Wrists, Elbows, Shoulders) (18 dims)
        vel_joints = ["LEFT_WRIST", "RIGHT_WRIST", "LEFT_ELBOW", "RIGHT_ELBOW", "LEFT_SHOULDER", "RIGHT_SHOULDER"]
        prev_record = self.history.get(person_id, [])
        prev_coords: Dict[str, np.ndarray] = {}
        prev_velocities: Dict[str, np.ndarray] = {}
        temporal_delta_ms: Optional[int] = None
        temporal_status = "INITIAL_FRAME"
        dt_sec: Optional[float] = None
        if prev_record:
            prev_t, prev_coords, prev_velocities = prev_record[-1]
            temporal_delta_ms = timestamp_ms - prev_t
            if temporal_delta_ms > 0:
                dt_sec = temporal_delta_ms / 1000.0
                temporal_status = "VALID_TEMPORAL_DELTA"
            else:
                temporal_status = "INVALID_TIMESTAMP_ORDER"

        displacements: Dict[str, List[float]] = {}
        velocities: Dict[str, List[float]] = {}
        accelerations: Dict[str, List[float]] = {}
        current_velocities: Dict[str, np.ndarray] = {}
        for j_name in vel_joints:
            has_curr = j_name in curr_coords
            has_prev = j_name in prev_coords
            if has_curr and has_prev and dt_sec is not None:
                displacement = compute_displacement_3d(prev_coords[j_name], curr_coords[j_name])
                vel = compute_velocity_3d(prev_coords[j_name], curr_coords[j_name], dt_sec)
                assert vel is not None
                displacements[j_name] = [float(v) for v in displacement]
                velocities[j_name] = [float(v) for v in vel]
                current_velocities[j_name] = vel
                if j_name in prev_velocities:
                    acceleration = compute_acceleration_3d(prev_velocities[j_name], vel, dt_sec)
                    if acceleration is not None:
                        accelerations[j_name] = [float(v) for v in acceleration]
                features.extend([float(vel[0]), float(vel[1]), float(vel[2])])
                mask.extend([1.0, 1.0, 1.0])
            else:
                features.extend([0.0, 0.0, 0.0])
                mask.extend([0.0, 0.0, 0.0])
            feature_names.extend([f"{j_name}_VX", f"{j_name}_VY", f"{j_name}_VZ"])

        # 3. Kinematic Angles (6 dims)
            kinematics = self.kin_extractor.extract(pose)
        expected_angles = [
            "LEFT_ELBOW_FLEXION", "RIGHT_ELBOW_FLEXION",
            "LEFT_SHOULDER_ELEVATION", "RIGHT_SHOULDER_ELEVATION",
            "LEFT_KNEE_ANGLE", "RIGHT_KNEE_ANGLE"
        ]
        for a_name in expected_angles:
            if a_name in kinematics.joint_angles:
                features.append(kinematics.joint_angles[a_name] / 180.0) # Normalized to [0, 1]
                mask.append(1.0)
            else:
                features.append(0.0)
                mask.append(0.0)
            feature_names.append(a_name)

        # 4. Kinematic Distances (5 dims)
        expected_distances = [
            "WRIST_TO_WRIST", "LEFT_WRIST_TO_SHOULDER", "RIGHT_WRIST_TO_SHOULDER",
            "SHOULDER_SPAN", "HIP_SPAN"
        ]
        for d_name in expected_distances:
            if d_name in kinematics.joint_distances:
                features.append(kinematics.joint_distances[d_name])
                mask.append(1.0)
            else:
                features.append(0.0)
                mask.append(0.0)
            feature_names.append(d_name)

        # 5. Torso Orientation (Roll, Pitch, Yaw) (3 dims)
        orient = self.orient_estimator.compute_orientation(pose)
        if orient.is_valid and orient.roll_deg is not None and orient.pitch_deg is not None and orient.yaw_deg is not None:
            features.extend([orient.roll_deg / 180.0, orient.pitch_deg / 180.0, orient.yaw_deg / 180.0])
            mask.extend([1.0, 1.0, 1.0])
        else:
            features.extend([0.0, 0.0, 0.0])
            mask.extend([0.0, 0.0, 0.0])
        feature_names.extend(["TORSO_ROLL", "TORSO_PITCH", "TORSO_YAW"])

        # 6. Torso Centroid Velocity (3 dims)
        if dt_sec is not None and "LEFT_HIP" in curr_coords and "RIGHT_HIP" in curr_coords and "LEFT_HIP" in prev_coords and "RIGHT_HIP" in prev_coords:
            c_curr = 0.5 * (curr_coords["LEFT_HIP"] + curr_coords["RIGHT_HIP"])
            c_prev = 0.5 * (prev_coords["LEFT_HIP"] + prev_coords["RIGHT_HIP"])
            c_vel = compute_velocity_3d(c_prev, c_curr, dt_sec)
            assert c_vel is not None
            features.extend([float(c_vel[0]), float(c_vel[1]), float(c_vel[2])])
            mask.extend([1.0, 1.0, 1.0])
        else:
            features.extend([0.0, 0.0, 0.0])
            mask.extend([0.0, 0.0, 0.0])
        feature_names.extend(["TORSO_VEL_X", "TORSO_VEL_Y", "TORSO_VEL_Z"])

        # Update history
        if person_id not in self.history:
            self.history[person_id] = []
        if temporal_status != "INVALID_TIMESTAMP_ORDER":
            self.history.setdefault(person_id, []).append((timestamp_ms, curr_coords, current_velocities))
        if len(self.history[person_id]) > 60:
            self.history[person_id].pop(0)

        feat_arr = np.array(features, dtype=np.float32)
        mask_arr = np.array(mask, dtype=np.float32)
        avg_conf = float(np.mean(confidences)) if confidences else 0.0

        return FrameFeatureVector(
            timestamp_ms=timestamp_ms,
            frame_index=frame_idx,
            person_id=person_id,
            feature_vector=feat_arr,
            missingness_mask=mask_arr,
            confidence_score=avg_conf,
            feature_names=feature_names,
            coordinate_space=(next(iter(lms.values())).coordinate_space.value if lms else "NONE"),
            measurement_status=(
                "VALID_3D" if lms and any(lm.is_confident(self.min_confidence, self.min_confidence) for lm in lms.values())
                else "MISSING_3D_LANDMARKS"
            ) if temporal_status == "INITIAL_FRAME" else temporal_status,
            orientation_status=("VALID_3D_ORIENTATION" if orient.is_valid else "UNSUPPORTED_OR_INVALID_3D_ORIENTATION"),
            human_label=person_id if person_id in {"HUMAN_1", "HUMAN_2"} else None,
            temporal_delta_ms=temporal_delta_ms,
            displacements=displacements,
            velocities=velocities,
            accelerations=accelerations,
            kinematic_features={
                "joint_angles_deg": kinematics.joint_angles,
                "joint_distances_m": kinematics.joint_distances,
                "relative_unit_vectors": kinematics.relative_vectors,
            },
        )


class TemporalSequenceManager:
    """Buffers consecutive per-person frame feature vectors into sliding sequence windows."""

    def __init__(self, sequence_length: int = 30, step_size: int = 15):
        self.sequence_length = sequence_length
        self.step_size = step_size
        self.buffers: Dict[str, List[FrameFeatureVector]] = {}

    def add_frame_feature(
        self,
        feat: FrameFeatureVector,
        activity_label: int = 0,
        activity_name: str = "IDLE_MONITORING",
        recording_session_id: str = "SESSION_LIVE"
    ) -> Optional[TemporalSequenceSample]:
        """Adds a frame feature and returns a windowed sample if buffer reaches window length."""
        pid = feat.person_id
        if pid not in self.buffers:
            self.buffers[pid] = []
            
        if self.buffers[pid] and feat.timestamp_ms <= self.buffers[pid][-1].timestamp_ms:
            return None
        self.buffers[pid].append(feat)

        if len(self.buffers[pid]) >= self.sequence_length:
            window = self.buffers[pid][:self.sequence_length]
            self.buffers[pid] = self.buffers[pid][self.step_size:]

            feat_matrix = np.stack([f.feature_vector for f in window], axis=0)
            mask_matrix = np.stack([f.missingness_mask for f in window], axis=0)

            sample = TemporalSequenceSample(
                sequence_id=f"{recording_session_id}_{pid}_{window[0].timestamp_ms}",
                person_id=pid,
                recording_session_id=recording_session_id,
                activity_label=activity_label,
                activity_name=activity_name,
                features=feat_matrix,
                missingness_mask=mask_matrix,
                start_timestamp_ms=window[0].timestamp_ms,
                end_timestamp_ms=window[-1].timestamp_ms,
                frame_ids=[f.frame_id for f in window],
                timestamps_ms=[f.timestamp_ms for f in window],
                coordinate_space=window[0].coordinate_space,
                measurement_statuses=[f.measurement_status for f in window],
                human_label=window[0].human_label,
            )
            return sample

        return None
