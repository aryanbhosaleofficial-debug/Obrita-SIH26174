"""Tracking types and life-cycle definitions for Human 1 and Human 2."""

from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional
import numpy as np

from .spatial_types import PersonPose3D


class TrackState(str, Enum):
    """Lifecycle state machine for tracked human slots."""
    TENTATIVE = "TENTATIVE"    # Detected once, awaiting confirmation across consecutive frames
    CONFIRMED = "CONFIRMED"    # Positively associated across sufficient frames
    COASTING = "COASTING"      # Temporarily lost or occluded, holding position/velocity state
    DELETED = "DELETED"        # Exceeded max coasting duration; slot released


@dataclass
class TrackedPerson:
    """Persistent tracking state for a single human subject slot (Human 1 / Human 2)."""
    track_id: int
    slot_id: str                      # "HUMAN_1" or "HUMAN_2"
    state: TrackState = TrackState.TENTATIVE
    hits: int = 1                     # Total successful detection associations
    age: int = 1                      # Total frames since initialization
    lost_frames: int = 0              # Consecutive frames missed
    last_pose: Optional[PersonPose3D] = None
    last_centroid_3d: Optional[np.ndarray] = None  # Torso/Hips 3D center of mass
    last_centroid_2d: Optional[np.ndarray] = None  # Normalized image (x, y)
    velocity_3d: Optional[np.ndarray] = None       # Estimated 3D velocity vector (m/frame)
    history_poses: List[PersonPose3D] = field(default_factory=list)
    last_observed_timestamp_ms: Optional[int] = None

    def update_with_detection(
        self, pose: PersonPose3D, max_history: int = 120,
        observation_timestamp_ms: Optional[int] = None
    ):
        self.hits += 1
        self.age += 1
        self.lost_frames = 0
        self.last_pose = pose
        self.last_observed_timestamp_ms = (
            pose.timestamp_ms if observation_timestamp_ms is None else observation_timestamp_ms
        )
        pose.person_id = self.slot_id
        pose.is_tracked = True
        
        # Calculate centroids
        # 3D Torso centroid: midpoint of left & right hip or shoulders
        lh = pose.get_joint_coords("LEFT_HIP")
        rh = pose.get_joint_coords("RIGHT_HIP")
        if lh is None or rh is None:
            lh = pose.get_joint_coords("LEFT_SHOULDER")
            rh = pose.get_joint_coords("RIGHT_SHOULDER")
        if lh is not None and rh is not None:
            new_centroid_3d = 0.5 * (lh + rh)
        else:
            new_centroid_3d = None
            
        if new_centroid_3d is not None and self.last_centroid_3d is not None and self.age > 1:
            self.velocity_3d = new_centroid_3d - self.last_centroid_3d
        if new_centroid_3d is not None:
            self.last_centroid_3d = new_centroid_3d
        
        if pose.bbox_2d is not None:
            xmin, ymin, xmax, ymax = pose.bbox_2d
            self.last_centroid_2d = np.array([0.5 * (xmin + xmax), 0.5 * (ymin + ymax)], dtype=np.float32)
            
        self.history_poses.append(pose)
        if len(self.history_poses) > max_history:
            self.history_poses.pop(0)

    def mark_missed(self):
        self.age += 1
        self.lost_frames += 1
        self.last_observed_timestamp_ms = None
        if self.state == TrackState.CONFIRMED:
            self.state = TrackState.COASTING


@dataclass
class TrackingResult:
    """Consolidated tracking frame result."""
    frame_index: int
    timestamp_ms: int
    active_tracks: Dict[str, TrackedPerson] = field(default_factory=dict)
    unassigned_detections: List[PersonPose3D] = field(default_factory=list)
