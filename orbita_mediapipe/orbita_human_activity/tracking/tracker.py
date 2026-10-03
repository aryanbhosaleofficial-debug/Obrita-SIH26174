"""Multi-person tracker managing persistent Human 1 and Human 2 tracks."""

from typing import Dict, List, Optional
import numpy as np

from ..schemas.spatial_types import PersonPose3D
from ..schemas.tracking_types import TrackState, TrackedPerson, TrackingResult
from .association import SpatialAssociationCost
from .identity_policy import IdentityPolicyManager


class MultiPersonTracker:
    """Maintains persistent tracking identities for up to two humans (HUMAN_1 and HUMAN_2)."""

    def __init__(
        self,
        max_persons: int = 2,
        max_lost_frames: int = 15,
        min_hits_to_confirm: int = 2,
        association_cost: Optional[SpatialAssociationCost] = None,
        assignment_policy: str = "SPATIAL_LEFT_RIGHT"
    ):
        self.max_persons = max_persons
        self.association_cost = association_cost or SpatialAssociationCost()
        self.policy_manager = IdentityPolicyManager(
            max_slots=max_persons,
            max_lost_frames=max_lost_frames,
            min_hits_to_confirm=min_hits_to_confirm,
            assignment_policy=assignment_policy,
        )
        # Active tracks indexed by slot ID ("HUMAN_1", "HUMAN_2")
        self.tracks: Dict[str, TrackedPerson] = {}
        self.track_counter = 0
        self.frame_index = 0
        self.last_timestamp_ms = 0

    def update(
        self,
        detections: List[PersonPose3D],
        timestamp_ms: int
    ) -> TrackingResult:
        """Processes new pose detections and updates Human 1 and Human 2 tracks.
        
        Args:
            detections: List of PersonPose3D detected in the current frame.
            timestamp_ms: Current frame timestamp.
            
        Returns:
            TrackingResult containing active tracks and any unassigned detections.
        """
        self.frame_index += 1
        dt_seconds = 0.033
        if self.last_timestamp_ms > 0 and timestamp_ms > self.last_timestamp_ms:
            dt_seconds = max((timestamp_ms - self.last_timestamp_ms) / 1000.0, 1e-3)
        self.last_timestamp_ms = timestamp_ms

        track_list = list(self.tracks.values())
        
        # 1. Match active tracks with current detections
        matches, unmatched_tracks_idx, unmatched_dets_idx = self.association_cost.match(
            tracks=track_list,
            detections=detections,
            dt_seconds=dt_seconds
        )

        # 2. Update matched tracks
        for t_idx, d_idx in matches:
            track = track_list[t_idx]
            det = detections[d_idx]
            track.update_with_detection(det, observation_timestamp_ms=timestamp_ms)
            track.state = self.policy_manager.evaluate_track_state(track)

        # 3. Handle unmatched tracks (missed detections / occlusion)
        for t_idx in unmatched_tracks_idx:
            track = track_list[t_idx]
            track.mark_missed()
            track.state = self.policy_manager.evaluate_track_state(track)

        # 4. Remove expired tracks
        expired_slots = [slot for slot, tr in self.tracks.items() if tr.state == TrackState.DELETED]
        for slot in expired_slots:
            del self.tracks[slot]

        # 5. Handle unmatched detections (new subjects entering scene)
        unassigned_detections: List[PersonPose3D] = []
        ordered_unmatched_dets = self.policy_manager.order_new_detections(detections, unmatched_dets_idx)
        for d_idx in ordered_unmatched_dets:
            det = detections[d_idx]
            active_slots = list(self.tracks.keys())
            new_slot = self.policy_manager.allocate_slot(active_slots)
            
            if new_slot is not None and len(self.tracks) < self.max_persons:
                self.track_counter += 1
                new_track = TrackedPerson(
                    track_id=self.track_counter,
                    slot_id=new_slot,
                    state=TrackState.TENTATIVE
                )
                new_track.update_with_detection(det, observation_timestamp_ms=timestamp_ms)
                new_track.state = self.policy_manager.evaluate_track_state(new_track)
                self.tracks[new_slot] = new_track
            else:
                unassigned_detections.append(det)

        return TrackingResult(
            frame_index=self.frame_index,
            timestamp_ms=timestamp_ms,
            active_tracks={slot: tr for slot, tr in self.tracks.items()},
            unassigned_detections=unassigned_detections
        )
