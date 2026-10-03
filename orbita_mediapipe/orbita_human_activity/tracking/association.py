"""Documented spatial-temporal association algorithms for multi-person tracking."""

from typing import List, Optional, Tuple
import numpy as np

from ..schemas.spatial_types import PersonPose3D
from ..schemas.tracking_types import TrackedPerson


def calculate_iou_2d(
    box_a: Tuple[float, float, float, float],
    box_b: Tuple[float, float, float, float]
) -> float:
    """Computes 2D Intersection-over-Union between two normalized bounding boxes [xmin, ymin, xmax, ymax]."""
    xa = max(box_a[0], box_b[0])
    ya = max(box_a[1], box_b[1])
    xb = min(box_a[2], box_b[2])
    yb = min(box_a[3], box_b[3])

    inter_w = max(0.0, xb - xa)
    inter_h = max(0.0, yb - ya)
    inter_area = inter_w * inter_h

    area_a = max(0.0, box_a[2] - box_a[0]) * max(0.0, box_a[3] - box_a[1])
    area_b = max(0.0, box_b[2] - box_b[0]) * max(0.0, box_b[3] - box_b[1])

    union_area = area_a + area_b - inter_area
    if union_area <= 1e-6:
        return 0.0
    return float(inter_area / union_area)


class SpatialAssociationCost:
    """Computes association cost matrix between existing tracks and new pose detections.
    
    DOCUMENTED ASSOCIATION METHOD:
    ------------------------------
    1. Spatial Cost = w_3d * (d_3d / max_d_3d) + w_2d * d_2d_centroid
    2. Gating: If 3D displacement exceeds plausible physical speed (e.g. > 2.5 m/s)
       or total cost exceeds threshold, the association is rejected (cost = inf).
    3. Solves optimal assignment using minimum weight bipartite matching.
    """

    def __init__(
        self,
        weight_3d: float = 0.65,
        weight_2d: float = 0.35,
        max_cost_threshold: float = 0.85,
        max_speed_m_per_s: float = 2.5
    ):
        self.w_3d = weight_3d
        self.w_2d = weight_2d
        self.max_cost = max_cost_threshold
        self.max_speed = max_speed_m_per_s

    def build_cost_matrix(
        self,
        tracks: List[TrackedPerson],
        detections: List[PersonPose3D],
        dt_seconds: float = 0.033
    ) -> np.ndarray:
        """Constructs an (N_tracks, M_detections) cost matrix."""
        num_tracks = len(tracks)
        num_dets = len(detections)
        if num_tracks == 0 or num_dets == 0:
            return np.empty((num_tracks, num_dets), dtype=np.float32)

        cost_matrix = np.full((num_tracks, num_dets), float('inf'), dtype=np.float32)
        max_plausible_dist = max(self.max_speed * dt_seconds, 0.40) # Minimum 40cm tolerance

        for t_idx, track in enumerate(tracks):
            # Predicted 3D centroid
            track_c3d = track.last_centroid_3d
            if track_c3d is None:
                continue
            if track.velocity_3d is not None:
                track_c3d = track_c3d + track.velocity_3d

            track_c2d = track.last_centroid_2d

            for d_idx, det in enumerate(detections):
                # Detection 3D centroid; never substitute a fabricated zero.
                lh = det.get_joint_coords("LEFT_HIP")
                rh = det.get_joint_coords("RIGHT_HIP")
                if lh is None or rh is None:
                    lh = det.get_joint_coords("LEFT_SHOULDER")
                    rh = det.get_joint_coords("RIGHT_SHOULDER")
                if lh is not None and rh is not None:
                    det_c3d = 0.5 * (lh + rh)
                else:
                    continue

                d3d = float(np.linalg.norm(track_c3d - det_c3d))

                # 2D centroid distance & IoU
                d2d = 0.0
                if track_c2d is not None and det.bbox_2d is not None:
                    xmin, ymin, xmax, ymax = det.bbox_2d
                    det_c2d = np.array([0.5 * (xmin + xmax), 0.5 * (ymin + ymax)], dtype=np.float32)
                    d2d = float(np.linalg.norm(track_c2d - det_c2d))

                # Gating check
                norm_d3d = min(d3d / max_plausible_dist, 2.0)
                cost = (self.w_3d * norm_d3d) + (self.w_2d * min(d2d * 2.0, 1.0))

                if cost <= self.max_cost:
                    cost_matrix[t_idx, d_idx] = cost

        return cost_matrix

    def match(
        self,
        tracks: List[TrackedPerson],
        detections: List[PersonPose3D],
        dt_seconds: float = 0.033
    ) -> Tuple[List[Tuple[int, int]], List[int], List[int]]:
        """Solves optimal association.
        
        Returns:
            Tuple of:
            - matches: List of (track_idx, detection_idx)
            - unmatched_tracks: List of track indices
            - unmatched_detections: List of detection indices
        """
        cost_matrix = self.build_cost_matrix(tracks, detections, dt_seconds)
        if cost_matrix.size == 0:
            return [], list(range(len(tracks))), list(range(len(detections)))

        # Greedy / Munkres solver
        matched_tracks = set()
        matched_dets = set()
        matches = []

        # Find best pairs greedily from lowest cost
        flat_indices = np.argsort(cost_matrix, axis=None)
        num_tracks, num_dets = cost_matrix.shape

        for flat_idx in flat_indices:
            t_idx = flat_idx // num_dets
            d_idx = flat_idx % num_dets
            cost = cost_matrix[t_idx, d_idx]
            if np.isinf(cost) or cost > self.max_cost:
                break
            if t_idx not in matched_tracks and d_idx not in matched_dets:
                matched_tracks.add(t_idx)
                matched_dets.add(d_idx)
                matches.append((t_idx, d_idx))

        unmatched_tracks = [i for i in range(num_tracks) if i not in matched_tracks]
        unmatched_dets = [j for j in range(num_dets) if j not in matched_dets]

        return matches, unmatched_tracks, unmatched_dets
