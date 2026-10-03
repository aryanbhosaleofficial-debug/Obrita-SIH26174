"""Task 1 tests for basic 3D skeleton and trajectory rendering."""

import unittest
import numpy as np

from orbita_human_activity.pipeline.visualizer import TrajectoryVisualizer3D
from orbita_human_activity.schemas.spatial_types import (
    CoordinateSpace,
    Landmark3D,
    PersonPose3D,
)
from orbita_human_activity.schemas.tracking_types import TrackState, TrackedPerson


class TestTask1Visualizer(unittest.TestCase):
    def test_renders_skeleton_and_trajectory(self):
        landmarks = [
            Landmark3D(11, "LEFT_SHOULDER", -0.2, 0.4, 0.0, coordinate_space=CoordinateSpace.MEDIAPIPE_WORLD),
            Landmark3D(12, "RIGHT_SHOULDER", 0.2, 0.4, 0.0, coordinate_space=CoordinateSpace.MEDIAPIPE_WORLD),
            Landmark3D(23, "LEFT_HIP", -0.1, -0.1, 0.0, coordinate_space=CoordinateSpace.MEDIAPIPE_WORLD),
            Landmark3D(24, "RIGHT_HIP", 0.1, -0.1, 0.0, coordinate_space=CoordinateSpace.MEDIAPIPE_WORLD),
        ]
        pose = PersonPose3D(timestamp_ms=100, frame_index=1, person_id="HUMAN_1", world_landmarks=landmarks)
        track = TrackedPerson(track_id=1, slot_id="HUMAN_1", state=TrackState.CONFIRMED, last_pose=pose)
        track.last_centroid_3d = np.array([0.0, 0.15, 0.0], dtype=np.float32)

        visualizer = TrajectoryVisualizer3D(enable_gui=False)
        figure = visualizer.render_tracks({"HUMAN_1": track})

        self.assertIsNotNone(figure)
        self.assertIsNotNone(visualizer.ax)
        self.assertGreaterEqual(len(visualizer.ax.lines), 1)
        self.assertEqual(len(visualizer.trajectories["HUMAN_1"]), 1)


if __name__ == "__main__":
    unittest.main()
