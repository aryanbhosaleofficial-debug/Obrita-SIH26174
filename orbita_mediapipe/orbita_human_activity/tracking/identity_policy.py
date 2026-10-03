"""Identity assignment policy and lifecycle management for Human 1 and Human 2."""

from typing import Dict, List, Optional
from ..schemas.tracking_types import TrackState, TrackedPerson


class IdentityPolicyManager:
    """Manages persistent tracking slot assignment (HUMAN_1 and HUMAN_2).
    
    SYSTEM ASSUMPTIONS & DOCUMENTED LIMITATIONS (Task 3 Requirement):
    -----------------------------------------------------------------
    1. Short-Term Tracking vs Long-Term Recognition:
       This module implements short-term spatial-temporal continuity. It maintains
       stable Human 1 and Human 2 tracks across brief occlusions (up to max_lost_frames).
       It does NOT perform face recognition, clothing-based appearance re-ID, or
       biometric identification. If an astronaut leaves the field of view for
       extended periods, re-entry identity cannot be guaranteed without biometric re-ID.
    2. Occlusion Coasting:
       During temporary occlusions (e.g. crossing behind equipment or another person),
       the track enters COASTING state. It extrapolates position using last known
       velocity for up to `max_lost_frames`.
    3. Re-entry & Priority Assignment:
       Slots are prioritized: HUMAN_1 is assigned first; HUMAN_2 is assigned second.
       A slot is only recycled when its track has expired (exceeded max_lost_frames).
    """

    def __init__(
        self,
        max_slots: int = 2,
        max_lost_frames: int = 15,
        min_hits_to_confirm: int = 2,
        assignment_policy: str = "SPATIAL_LEFT_RIGHT"
    ):
        self.max_slots = max_slots
        self.max_lost_frames = max_lost_frames
        self.min_hits = min_hits_to_confirm
        self.assignment_policy = assignment_policy
        self.available_slots = ["HUMAN_1", "HUMAN_2"]
        self.next_track_id = 1

    def allocate_slot(self, active_slots: List[str]) -> Optional[str]:
        """Finds the next available slot name (e.g. HUMAN_1 or HUMAN_2)."""
        for slot in self.available_slots:
            if slot not in active_slots:
                return slot
        return None

    def order_new_detections(self, detections, indices: List[int]) -> List[int]:
        """Order only new-slot allocation; established IDs come from association."""
        if self.assignment_policy == "FIRST_COME_FIRST_SERVE":
            return indices
        if self.assignment_policy != "SPATIAL_LEFT_RIGHT":
            raise ValueError(f"Unsupported assignment policy: {self.assignment_policy}")

        def x_center(index: int):
            bbox = detections[index].bbox_2d
            if bbox is not None:
                return 0.5 * (bbox[0] + bbox[2])
            left = detections[index].get_joint_coords("LEFT_HIP")
            right = detections[index].get_joint_coords("RIGHT_HIP")
            if left is None or right is None:
                left = detections[index].get_joint_coords("LEFT_SHOULDER")
                right = detections[index].get_joint_coords("RIGHT_SHOULDER")
            return float(0.5 * (left[0] + right[0])) if left is not None and right is not None else float("inf")

        return sorted(indices, key=x_center)

    def evaluate_track_state(self, track: TrackedPerson) -> TrackState:
        """Evaluates track lifecycle transitions."""
        if track.lost_frames > self.max_lost_frames:
            return TrackState.DELETED
        if track.lost_frames > 0:
            return TrackState.COASTING
        if track.hits >= self.min_hits:
            return TrackState.CONFIRMED
        return TrackState.TENTATIVE
