"""Focused Task 4 contract tests; all fixtures are synthetic software tests."""

import os
import tempfile
import unittest

import numpy as np
import torch
from torch.utils.data import DataLoader

from orbita_human_activity.models.bottleneck_network import OrbitaBottleneckHAR
from orbita_human_activity.schemas.dataset_types import TemporalSequenceSample
from orbita_human_activity.schemas.feature_types import FEATURE_SCHEMA_VERSION
from orbita_human_activity.training.dataset import OrbitaActivityDataset
from orbita_human_activity.training.trainer import OrbitaModelTrainer


class TestTask4Training(unittest.TestCase):
    def _samples(self, sessions=("S1", "S2")):
        return [TemporalSequenceSample(
            sequence_id=f"{session}_{i}", person_id="HUMAN_1" if i % 2 == 0 else "HUMAN_2",
            recording_session_id=session, activity_label=i % 2, activity_name="TEST",
            features=np.zeros((4, 74), dtype=np.float32),
            missingness_mask=np.ones((4, 74), dtype=np.float32),
            start_timestamp_ms=i * 100, end_timestamp_ms=i * 100 + 99,
        ) for i, session in enumerate(sessions)]

    def test_schema_dimensions_and_relu(self):
        model = OrbitaBottleneckHAR(input_dim=74, sequence_length=4,
                                    bottleneck_dim_1=12, bottleneck_dim_2=5,
                                    num_classes=3)
        self.assertEqual(model.feature_schema_version, FEATURE_SCHEMA_VERSION)
        self.assertIsInstance(model.activation, torch.nn.ReLU)
        logits, embedding = model(torch.zeros(2, 4, 74))
        self.assertEqual(logits.shape, (2, 3))
        self.assertEqual(embedding.shape, (2, 5))
        with self.assertRaises(ValueError):
            model(torch.zeros(2, 3, 74))

    def test_adam_checkpoint_round_trip_and_schema_guard(self):
        model = OrbitaBottleneckHAR(input_dim=74, sequence_length=4, num_classes=2)
        trainer = OrbitaModelTrainer(model, device="cpu")
        self.assertIsInstance(trainer.optimizer, torch.optim.Adam)
        loader = DataLoader(OrbitaActivityDataset(self._samples()), batch_size=2)
        trainer.train_epoch(loader)
        with tempfile.TemporaryDirectory() as directory:
            path = os.path.join(directory, "task4.pt")
            trainer.save_checkpoint(path, epoch=1, val_acc=0.0)
            restored = OrbitaModelTrainer(
                OrbitaBottleneckHAR(input_dim=74, sequence_length=4, num_classes=2),
                device="cpu")
            checkpoint = restored.load_checkpoint(path)
            self.assertEqual(checkpoint["feature_schema_version"], FEATURE_SCHEMA_VERSION)
            self.assertEqual(checkpoint["optimizer"], "Adam")

    def test_split_rejects_single_session_leakage(self):
        with self.assertRaises(ValueError):
            OrbitaActivityDataset.split_by_session(self._samples(("ONLY",)))

    def test_split_keeps_sessions_disjoint(self):
        samples = self._samples(("S1", "S2", "S3", "S4"))
        train, validation = OrbitaActivityDataset.split_by_session(samples, val_ratio=0.25)
        train_sessions = {s.recording_session_id for s in train.samples}
        val_sessions = {s.recording_session_id for s in validation.samples}
        self.assertTrue(train_sessions.isdisjoint(val_sessions))


if __name__ == "__main__":
    unittest.main()
