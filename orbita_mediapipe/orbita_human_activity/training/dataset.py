"""Structured JSONL-to-tensor dataset with strict session-based splitting."""

import json
from typing import Dict, List, Tuple
import numpy as np
import torch
from torch.utils.data import Dataset

from ..schemas.dataset_types import TemporalSequenceSample


class OrbitaActivityDataset(Dataset):
    """PyTorch Dataset holding temporal activity sequence samples.
    
    TEMPORAL LEAKAGE PREVENTION (Task 4 Requirement):
    -------------------------------------------------
    In temporal activity recognition, adjacent sliding windows often overlap
    by 50-75% (e.g. sharing 15-22 frames).
    If samples are randomly shuffled into train/val splits at the window level,
    nearly identical frames would exist in both training and validation sets,
    producing artificially inflated validation scores (data leakage).
    To prevent this, `split_by_session` partitions samples strictly by their
    `recording_session_id`.
    """

    def __init__(self, samples: List[TemporalSequenceSample]):
        self.samples = samples

    def __len__(self) -> int:
        return len(self.samples)

    def __getitem__(self, idx: int) -> Tuple[torch.Tensor, torch.Tensor, torch.Tensor]:
        sample = self.samples[idx]
        x = torch.from_numpy(sample.features).float()
        mask = torch.from_numpy(sample.missingness_mask).float()
        y = torch.tensor(sample.activity_label, dtype=torch.long)
        return x, mask, y

    @staticmethod
    def from_feature_jsonl(
        path: str,
        sequence_length: int = 30,
        step_size: int = 15,
        activity_label: int = 0,
        activity_name: str = "UNLABELED",
        recording_session_id: str = "JSONL_SESSION",
    ) -> "OrbitaActivityDataset":
        """Build deterministic, person-isolated tensor samples from feature JSONL.

        JSONL is the structured source of truth; CSV is not consumed here.
        Labels default to ``UNLABELED`` and require authoritative annotation
        before supervised training.
        """
        if sequence_length <= 0 or step_size <= 0:
            raise ValueError("sequence_length and step_size must be positive")
        grouped: Dict[str, List[dict]] = {}
        with open(path, "r", encoding="utf-8") as handle:
            for line in handle:
                if line.strip():
                    record = json.loads(line)
                    grouped.setdefault(str(record["person_id"]), []).append(record)

        samples: List[TemporalSequenceSample] = []
        for person_id in sorted(grouped):
            records = sorted(
                grouped[person_id],
                key=lambda item: (
                    int(item["timestamp_ms"]),
                    int(item.get("frame_id", item.get("frame_index", 0))),
                ),
            )
            for start in range(0, max(0, len(records) - sequence_length + 1), step_size):
                window = records[start:start + sequence_length]
                if len(window) != sequence_length:
                    continue
                samples.append(TemporalSequenceSample(
                    sequence_id=f"{recording_session_id}_{person_id}_{window[0]['timestamp_ms']}",
                    person_id=person_id,
                    recording_session_id=recording_session_id,
                    activity_label=activity_label,
                    activity_name=activity_name,
                    features=np.asarray([r["features"] for r in window], dtype=np.float32),
                    missingness_mask=np.asarray([r["missingness_mask"] for r in window], dtype=np.float32),
                    start_timestamp_ms=int(window[0]["timestamp_ms"]),
                    end_timestamp_ms=int(window[-1]["timestamp_ms"]),
                    frame_ids=[int(r.get("frame_id", r.get("frame_index", 0))) for r in window],
                    timestamps_ms=[int(r["timestamp_ms"]) for r in window],
                    coordinate_space=str(window[0].get("coordinate_space", "UNKNOWN")),
                    measurement_statuses=[str(r.get("measurement_status", "UNKNOWN")) for r in window],
                    human_label=window[0].get("human_label"),
                ))
        return OrbitaActivityDataset(samples)

    @staticmethod
    def split_by_session(
        samples: List[TemporalSequenceSample],
        val_ratio: float = 0.2,
        seed: int = 42
    ) -> Tuple['OrbitaActivityDataset', 'OrbitaActivityDataset']:
        """Splits samples into Train and Validation sets by distinct recording sessions."""
        sessions = sorted(list({s.recording_session_id for s in samples}))
        rng = np.random.RandomState(seed)
        rng.shuffle(sessions)

        num_val = max(1, int(len(sessions) * val_ratio))
        val_sessions = set(sessions[:num_val])
        train_sessions = set(sessions[num_val:])

        if not train_sessions:
            raise ValueError(
                "At least two recording sessions are required for a leakage-free "
                "train/validation split; refusing to reuse one session in both sets."
            )

        train_samples = [s for s in samples if s.recording_session_id in train_sessions]
        val_samples = [s for s in samples if s.recording_session_id in val_sessions]

        return OrbitaActivityDataset(train_samples), OrbitaActivityDataset(val_samples)
