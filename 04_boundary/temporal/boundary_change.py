"""Deterministic image-plane boundary states, not actions or physical contact."""

import math
from collections import deque

from shared.enums.boundary_state import BoundaryState

from .confirmation import StateConfirmation


class BoundaryStateClassifier:
    def __init__(self, config):
        self.config = config
        self.centroids = deque(maxlen=config.motion_min_frames)
        self.frame_ids = deque(maxlen=config.motion_min_frames)
        self.confirmation = StateConfirmation(
            config.confirmation_n, config.confirmation_m
        )
        self.reset()

    def reset(self):
        self.centroids.clear()
        self.frame_ids.clear()
        self.confirmation.reset()
        self.contact_anchor = None
        self.released_frames = 0

    def _motion(self):
        if len(self.centroids) < self.config.motion_min_frames:
            return BoundaryState.UNKNOWN
        steps = [
            math.dist(a, b) for a, b in zip(self.centroids, list(self.centroids)[1:])
        ]
        # Thresholds use pixels per original source frame, including dropped IDs.
        intervals = [b - a for a, b in zip(self.frame_ids, list(self.frame_ids)[1:])]
        normalized_steps = [
            distance / interval for distance, interval in zip(steps, intervals)
        ]
        if max(normalized_steps) <= self.config.stationary_tolerance_px:
            return BoundaryState.STATIONARY
        path = sum(steps)
        coherent = (
            math.dist(self.centroids[0], self.centroids[-1]) / path if path else 0
        )
        if (
            min(normalized_steps) >= self.config.moving_threshold_px
            and coherent >= self.config.min_motion_coherence
        ):
            return BoundaryState.MOVING
        return BoundaryState.UNKNOWN

    def update(self, centroid, interaction, *, frame_id: int):
        # Called only after the full geometry/upstream/rack quality gate.
        self.centroids.append(tuple(centroid))
        self.frame_ids.append(frame_id)
        motion = self._motion()
        contact = (
            bool(interaction.get("near_boundary", False))
            and interaction.get("contact_proxy", 0)
            >= self.config.contact_min_confidence
        )
        hand_id = interaction.get("hand_id")
        distance = interaction.get("distance_to_boundary")
        candidate = BoundaryState.CONTACT if contact else motion
        if not contact and self.contact_anchor is not None:
            self.released_frames += 1
            anchor_hand, anchor_distance = self.contact_anchor
            if self.released_frames > self.config.confirmation_m:
                self.contact_anchor = None
            elif (
                interaction.get("available", False)
                and hand_id == anchor_hand
                and distance is not None
                and distance
                >= anchor_distance + self.config.separation_distance_increase_px
                and not interaction.get("near_boundary", False)
                and motion == BoundaryState.MOVING
            ):
                candidate = BoundaryState.SEPARATING
        state, confirmed, count = self.confirmation.update(candidate)
        if confirmed and state == BoundaryState.CONTACT:
            self.contact_anchor = (hand_id, distance) if hand_id is not None else None
            self.released_frames = 0
        return state, confirmed, count
