"""Kinematic feature calculation from 3D anatomical landmarks."""

from typing import Dict, List, Optional, Tuple
import numpy as np

from ..schemas.spatial_types import Landmark3D, PersonPose3D
from ..schemas.feature_types import KinematicFeatures


def compute_angle_3d(p_a: np.ndarray, p_b: np.ndarray, p_c: np.ndarray) -> Optional[float]:
    """Computes the 3D angle at vertex B formed by rays B->A and B->C in degrees [0, 180]."""
    v_ba = p_a - p_b
    v_bc = p_c - p_b
    norm_ba = np.linalg.norm(v_ba)
    norm_bc = np.linalg.norm(v_bc)
    if norm_ba < 1e-6 or norm_bc < 1e-6:
        return None
    cos_theta = np.dot(v_ba, v_bc) / (norm_ba * norm_bc)
    cos_theta = np.clip(cos_theta, -1.0, 1.0)
    return float(np.degrees(np.arccos(cos_theta)))


def compute_distance_3d(p_a: np.ndarray, p_b: np.ndarray) -> float:
    """Computes Euclidean distance between two 3D points in meters."""
    return float(np.linalg.norm(p_a - p_b))


def compute_displacement_3d(p_previous: np.ndarray, p_current: np.ndarray) -> np.ndarray:
    """Return frame-to-frame displacement in the input coordinate-space units."""
    return np.asarray(p_current, dtype=np.float32) - np.asarray(p_previous, dtype=np.float32)


def compute_velocity_3d(
    p_previous: np.ndarray, p_current: np.ndarray, delta_t_seconds: float
) -> Optional[np.ndarray]:
    """Return timestamp-derived velocity, or ``None`` for an invalid interval."""
    if delta_t_seconds <= 0.0:
        return None
    return compute_displacement_3d(p_previous, p_current) / float(delta_t_seconds)


def compute_acceleration_3d(
    velocity_previous: np.ndarray, velocity_current: np.ndarray, delta_t_seconds: float
) -> Optional[np.ndarray]:
    """Return acceleration only when two valid velocity samples have a positive interval."""
    if delta_t_seconds <= 0.0:
        return None
    return (np.asarray(velocity_current, dtype=np.float32) - np.asarray(velocity_previous, dtype=np.float32)) / float(delta_t_seconds)


def compute_unit_vector_3d(p_src: np.ndarray, p_dst: np.ndarray) -> Tuple[List[float], float]:
    """Computes normalized unit vector from src to dst and its magnitude."""
    diff = p_dst - p_src
    mag = float(np.linalg.norm(diff))
    if mag < 1e-6:
        return [0.0, 0.0, 0.0], 0.0
    unit_vec = (diff / mag).tolist()
    return unit_vec, mag


class KinematicExtractor:
    """Extracts geometric, distance, and angular features from 3D landmarks."""

    def __init__(self, min_confidence: float = 0.5):
        self.min_confidence = min_confidence

    def extract(self, pose: PersonPose3D) -> KinematicFeatures:
        """Extracts kinematic features while strictly tracking missing/low-confidence joints."""
        lms = pose.landmark_map
        angles: Dict[str, float] = {}
        distances: Dict[str, float] = {}
        rel_vectors: Dict[str, List[float]] = {}

        def get_valid_joint(name: str) -> Optional[np.ndarray]:
            lm = lms.get(name)
            if lm is None or not lm.is_confident(self.min_confidence, self.min_confidence):
                return None
            return lm.to_numpy()

        # Key Joints
        lw = get_valid_joint("LEFT_WRIST")
        le = get_valid_joint("LEFT_ELBOW")
        ls = get_valid_joint("LEFT_SHOULDER")
        rw = get_valid_joint("RIGHT_WRIST")
        re = get_valid_joint("RIGHT_ELBOW")
        rs = get_valid_joint("RIGHT_SHOULDER")
        lh = get_valid_joint("LEFT_HIP")
        rh = get_valid_joint("RIGHT_HIP")
        lk = get_valid_joint("LEFT_KNEE")
        la = get_valid_joint("LEFT_ANKLE")
        rk = get_valid_joint("RIGHT_KNEE")
        ra = get_valid_joint("RIGHT_ANKLE")

        # 1. Joint Angles
        if ls is not None and le is not None and lw is not None:
            val = compute_angle_3d(ls, le, lw)
            if val is not None: angles["LEFT_ELBOW_FLEXION"] = val

        if rs is not None and re is not None and rw is not None:
            val = compute_angle_3d(rs, re, rw)
            if val is not None: angles["RIGHT_ELBOW_FLEXION"] = val

        if lh is not None and ls is not None and le is not None:
            val = compute_angle_3d(lh, ls, le)
            if val is not None: angles["LEFT_SHOULDER_ELEVATION"] = val

        if rh is not None and rs is not None and re is not None:
            val = compute_angle_3d(rh, rs, re)
            if val is not None: angles["RIGHT_SHOULDER_ELEVATION"] = val

        if lh is not None and lk is not None and la is not None:
            val = compute_angle_3d(lh, lk, la)
            if val is not None: angles["LEFT_KNEE_ANGLE"] = val

        if rh is not None and rk is not None and ra is not None:
            val = compute_angle_3d(rh, rk, ra)
            if val is not None: angles["RIGHT_KNEE_ANGLE"] = val

        # 2. Inter-joint Distances
        if lw is not None and rw is not None:
            distances["WRIST_TO_WRIST"] = compute_distance_3d(lw, rw)
        if lw is not None and ls is not None:
            distances["LEFT_WRIST_TO_SHOULDER"] = compute_distance_3d(lw, ls)
        if rw is not None and rs is not None:
            distances["RIGHT_WRIST_TO_SHOULDER"] = compute_distance_3d(rw, rs)
        if ls is not None and rs is not None:
            distances["SHOULDER_SPAN"] = compute_distance_3d(ls, rs)
        if lh is not None and rh is not None:
            distances["HIP_SPAN"] = compute_distance_3d(lh, rh)

        # 3. Relative Direction Vectors
        if le is not None and lw is not None:
            uv, _ = compute_unit_vector_3d(le, lw)
            rel_vectors["LEFT_FOREARM_DIR"] = uv
        if re is not None and rw is not None:
            uv, _ = compute_unit_vector_3d(re, rw)
            rel_vectors["RIGHT_FOREARM_DIR"] = uv
        if ls is not None and le is not None:
            uv, _ = compute_unit_vector_3d(ls, le)
            rel_vectors["LEFT_ARM_DIR"] = uv
        if rs is not None and re is not None:
            uv, _ = compute_unit_vector_3d(rs, re)
            rel_vectors["RIGHT_ARM_DIR"] = uv

        return KinematicFeatures(
            joint_angles=angles,
            joint_distances=distances,
            relative_vectors=rel_vectors
        )
