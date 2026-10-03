"""Optional 3D landmark and trajectory visualizer for ORBITA."""

from typing import Dict, List, Optional
import numpy as np

from ..schemas.spatial_types import Landmark3D, PersonPose3D
from ..schemas.tracking_types import TrackedPerson


# Standard skeletal connection pairs for 3D rendering
POSE_CONNECTIONS = [
    ("LEFT_SHOULDER", "RIGHT_SHOULDER"),
    ("LEFT_SHOULDER", "LEFT_ELBOW"),
    ("LEFT_ELBOW", "LEFT_WRIST"),
    ("RIGHT_SHOULDER", "RIGHT_ELBOW"),
    ("RIGHT_ELBOW", "RIGHT_WRIST"),
    ("LEFT_SHOULDER", "LEFT_HIP"),
    ("RIGHT_SHOULDER", "RIGHT_HIP"),
    ("LEFT_HIP", "RIGHT_HIP"),
    ("LEFT_HIP", "LEFT_KNEE"),
    ("LEFT_KNEE", "LEFT_ANKLE"),
    ("RIGHT_HIP", "RIGHT_KNEE"),
    ("RIGHT_KNEE", "RIGHT_ANKLE"),
]


class TrajectoryVisualizer3D:
    """Provides basic 3D skeleton/trajectory visualization and ASCII summaries."""

    def __init__(self, enable_gui: bool = False):
        self.enable_gui = enable_gui
        self.fig = None
        self.ax = None
        self.trajectories: Dict[str, List[np.ndarray]] = {}
        if enable_gui:
            try:
                import matplotlib.pyplot as plt
                self.fig = plt.figure(figsize=(8, 6))
                self.ax = self.fig.add_subplot(111, projection='3d')
            except Exception as e:
                print(f"[ORBITA Visualizer] Could not initialize Matplotlib 3D: {e}")
                self.enable_gui = False

    def render_tracks(self, tracks: Dict[str, TrackedPerson]):
        """Render current 3D skeletons and centroid trajectories.

        This is a visualization aid only. Coordinates retain the frame selected
        by ``PersonPose3D`` and are never treated as rack-calibrated unless their
        metadata says ``RACK_RELATIVE_CALIBRATED``.
        """
        if self.ax is None:
            try:
                import matplotlib.pyplot as plt
                self.fig = plt.figure(figsize=(8, 6))
                self.ax = self.fig.add_subplot(111, projection="3d")
            except Exception as exc:
                raise RuntimeError("Matplotlib 3D visualization is unavailable") from exc

        self.ax.cla()
        colors = ["tab:blue", "tab:red", "tab:green", "tab:orange"]
        for color_index, (slot, track) in enumerate(tracks.items()):
            pose = track.last_pose
            if pose is None:
                continue
            landmarks = pose.landmark_map
            color = colors[color_index % len(colors)]
            for start_name, end_name in POSE_CONNECTIONS:
                start = landmarks.get(start_name)
                end = landmarks.get(end_name)
                if start is not None and end is not None:
                    self.ax.plot(
                        [start.x, end.x], [start.y, end.y], [start.z, end.z],
                        color=color, linewidth=2
                    )

            centroid = track.last_centroid_3d
            if centroid is not None:
                history = self.trajectories.setdefault(slot, [])
                history.append(np.asarray(centroid, dtype=np.float32).copy())
                history[:] = history[-120:]
                path = np.stack(history)
                self.ax.plot(path[:, 0], path[:, 1], path[:, 2], color=color, linestyle="--")
                self.ax.scatter([centroid[0]], [centroid[1]], [centroid[2]], color=color, label=slot)

        self.ax.set_xlabel("X")
        self.ax.set_ylabel("Y")
        self.ax.set_zlabel("Z")
        if tracks:
            self.ax.legend(loc="upper right")
        return self.fig

    def render_frame_ascii(
        self,
        frame_idx: int,
        tracks: Dict[str, TrackedPerson]
    ) -> str:
        """Produces a lightweight ASCII status representation of the 3D scene."""
        lines = [f"--- Frame {frame_idx:04d} | Active Subjects: {len(tracks)} ---"]
        for slot, tr in tracks.items():
            c3d = tr.last_centroid_3d
            c_str = f"({c3d[0]:.2f}, {c3d[1]:.2f}, {c3d[2]:.2f})m" if c3d is not None else "(N/A)"
            lines.append(f"  [{slot}] State: {tr.state.value:<9} | Hits: {tr.hits:<3} | Lost: {tr.lost_frames:<2} | 3D Centroid: {c_str}")
        return "\n".join(lines)
