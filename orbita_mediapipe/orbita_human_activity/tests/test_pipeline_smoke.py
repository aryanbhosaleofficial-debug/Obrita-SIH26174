"""Integration smoke test for end-to-end ORBITA HAR pipeline."""

import os
import shutil
import unittest
import json

from orbita_human_activity.pipeline.orbita_pipeline import OrbitaHARPipeline
from orbita_human_activity.pipeline.serialization import DataLogger


class TestPipelineSmoke(unittest.TestCase):

    def setUp(self):
        self.test_log_dir = "test_output_logs"
        self.logger = DataLogger(output_dir=self.test_log_dir, session_id="SMOKE_TEST")
        self.pipeline = OrbitaHARPipeline(logger=self.logger, sequence_length=30)

    def tearDown(self):
        if os.path.exists(self.test_log_dir):
            shutil.rmtree(self.test_log_dir, ignore_errors=True)

    def test_pipeline_execution(self):
        """Runs 35 frames through full pipeline to trigger sequence creation and classification."""
        result = self.pipeline.run_smoke_pipeline(num_frames=35)
        self.assertEqual(result["status"], "SUCCESS")
        self.assertEqual(result["frames_processed"], 35)

        # Check logs written
        self.assertTrue(os.path.exists(self.logger.features_jsonl_path))
        self.assertTrue(os.path.exists(self.logger.predictions_jsonl_path))
        self.assertTrue(os.path.exists(self.logger.predictions_csv_path))

        # Check at least one frame feature was logged
        with open(self.logger.features_jsonl_path, "r", encoding="utf-8") as f:
            lines = f.readlines()
            self.assertGreater(len(lines), 0)
            first_record = json.loads(lines[0])
            self.assertEqual(first_record["feature_dim"], 74)
            self.assertIn(first_record["person_id"], ["HUMAN_1", "HUMAN_2"])


if __name__ == "__main__":
    unittest.main()
