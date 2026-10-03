"""Controlled synthetic verification of the four-task ORBITA interfaces."""

import json
import os
import shutil
import tempfile
import unittest

from orbita_human_activity.pipeline.orbita_pipeline import OrbitaHARPipeline
from orbita_human_activity.pipeline.serialization import DataLogger
from orbita_human_activity.schemas.feature_types import FEATURE_SCHEMA_VERSION


class _VisualizationSpy:
    enable_gui = False

    def __init__(self):
        self.received = []

    def render_tracks(self, tracks):
        self.received.append(dict(tracks))


class TestFourTaskIntegration(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.mkdtemp(prefix="orbita_integration_")
        self.logger = DataLogger(output_dir=self.directory, session_id="INTEGRATION")
        self.pipeline = OrbitaHARPipeline(
            logger=self.logger, sequence_length=30, enable_logging=True
        )
        self.visualizer = _VisualizationSpy()
        self.pipeline.visualizer = self.visualizer

    def tearDown(self):
        shutil.rmtree(self.directory, ignore_errors=True)

    def test_synthetic_four_task_path_preserves_people_and_metadata(self):
        result = self.pipeline.run_smoke_pipeline(num_frames=35)
        self.assertEqual(result["status"], "SUCCESS")
        self.assertFalse(self.pipeline.pose_runner.is_real_detector)
        self.assertEqual(self.pipeline.model.input_dim, 74)
        self.assertEqual(self.pipeline.model.feature_schema_version, FEATURE_SCHEMA_VERSION)
        self.assertTrue(self.visualizer.received)

        with open(self.logger.features_jsonl_path, encoding="utf-8") as handle:
            records = [json.loads(line) for line in handle if line.strip()]
        self.assertGreater(len(records), 0)
        person_ids = {record["person_id"] for record in records}
        self.assertEqual(person_ids, {"HUMAN_1", "HUMAN_2"})
        for person_id in person_ids:
            person_records = [r for r in records if r["person_id"] == person_id]
            timestamps = [r["timestamp_ms"] for r in person_records]
            self.assertEqual(timestamps, sorted(timestamps))
            self.assertTrue(all(r["frame_id"] >= 1 for r in person_records))
            self.assertTrue(all(r["feature_schema_version"] == FEATURE_SCHEMA_VERSION for r in person_records))
            self.assertTrue(all(r["feature_dim"] == 74 for r in person_records))
            self.assertTrue(all(r["human_label"] == person_id for r in person_records))

        latest_tracks = self.visualizer.received[-1]
        self.assertEqual(set(latest_tracks), {"HUMAN_1", "HUMAN_2"})
        for track in latest_tracks.values():
            self.assertIsNotNone(track.last_pose)
            self.assertTrue(track.last_pose.landmark_map)

    def test_inference_starts_only_after_causal_sequence_window(self):
        for frame in range(29):
            _, predictions = self.pipeline.process_frame(None, frame * 33)
            self.assertEqual(predictions, [])
        _, predictions = self.pipeline.process_frame(None, 29 * 33)
        self.assertGreaterEqual(len(predictions), 1)
        self.assertTrue(all(pred.timestamp_ms == 29 * 33 for pred in predictions))


if __name__ == "__main__":
    unittest.main()
