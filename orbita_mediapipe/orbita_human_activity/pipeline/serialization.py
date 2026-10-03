"""Documented JSONL and CSV logging for ORBITA outputs."""

import csv
import json
import os
from typing import Dict, List, Optional
from ..schemas.feature_types import FrameFeatureVector
from ..schemas.dataset_types import PredictionResult


class DataLogger:
    """Logs spatial features and activity recognition predictions to JSONL and CSV formats."""

    def __init__(
        self,
        output_dir: str = "output_logs",
        session_id: str = "SESSION_001"
    ):
        self.output_dir = output_dir
        self.session_id = session_id
        os.makedirs(output_dir, exist_ok=True)

        self.features_jsonl_path = os.path.join(output_dir, f"{session_id}_features.jsonl")
        self.features_csv_path = os.path.join(output_dir, f"{session_id}_features.csv")
        self.predictions_jsonl_path = os.path.join(output_dir, f"{session_id}_predictions.jsonl")
        self.predictions_csv_path = os.path.join(output_dir, f"{session_id}_predictions.csv")

        self._init_csv_headers()
        self._init_feature_csv_headers()

    def _init_csv_headers(self):
        """Initializes CSV header if file does not exist."""
        if not os.path.exists(self.predictions_csv_path):
            with open(self.predictions_csv_path, mode="w", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                writer.writerow([
                    "timestamp_ms",
                    "person_id",
                    "predicted_class_id",
                    "predicted_class_name",
                    "confidence",
                    "is_reliable",
                    "notes"
                ])

    def _init_feature_csv_headers(self):
        if not os.path.exists(self.features_csv_path):
            with open(self.features_csv_path, mode="w", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                writer.writerow([
                    "feature_schema_version", "timestamp_ms", "frame_id", "person_id",
                    "human_label", "coordinate_space", "measurement_status",
                    "orientation_status", "temporal_delta_ms", "feature_dim",
                    *[f"feature_{i}" for i in range(74)]
                ])

    def log_frame_feature(self, feature: FrameFeatureVector):
        """Appends a frame feature record to JSONL."""
        with open(self.features_jsonl_path, mode="a", encoding="utf-8") as f:
            f.write(json.dumps(feature.to_dict()) + "\n")
        with open(self.features_csv_path, mode="a", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            record = feature.to_dict()
            writer.writerow([
                record["feature_schema_version"], record["timestamp_ms"], record["frame_id"],
                record["person_id"], record["human_label"], record["coordinate_space"],
                record["measurement_status"], record["orientation_status"],
                record["temporal_delta_ms"], record["feature_dim"],
                *[float(value) for value in feature.feature_vector]
            ])

    def log_prediction(self, prediction: PredictionResult):
        """Logs prediction to both JSONL and CSV."""
        # 1. JSONL Log
        with open(self.predictions_jsonl_path, mode="a", encoding="utf-8") as f:
            f.write(json.dumps(prediction.to_dict()) + "\n")

        # 2. CSV Log
        with open(self.predictions_csv_path, mode="a", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow([
                prediction.timestamp_ms,
                prediction.person_id,
                prediction.predicted_class_id,
                prediction.predicted_class_name,
                prediction.confidence,
                prediction.is_reliable,
                prediction.notes or ""
            ])
