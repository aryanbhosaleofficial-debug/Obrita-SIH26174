"""Synthetic dataset generator and training smoke test for tensor execution verification."""

from typing import List
import numpy as np
import torch
from torch.utils.data import DataLoader

from ..schemas.dataset_types import TemporalSequenceSample
from ..models.bottleneck_network import OrbitaBottleneckHAR
from .dataset import OrbitaActivityDataset
from .trainer import OrbitaModelTrainer


def generate_synthetic_dataset(
    num_samples: int = 40,
    sequence_length: int = 30,
    feature_dim: int = 74,
    num_classes: int = 6,
    num_sessions: int = 4,
    seed: int = 42
) -> List[TemporalSequenceSample]:
    """Generates synthetic sequence samples solely for software testing.
    
    LABEL: SOFTWARE EXECUTION TEST ONLY - NOT MODEL PERFORMANCE EVIDENCE.
    """
    rng = np.random.RandomState(seed)
    samples: List[TemporalSequenceSample] = []
    class_names = [
        "IDLE_MONITORING", "RACK_INSPECTION", "SWITCH_ACTUATION",
        "CABLE_ROUTING", "EQUIPMENT_MAINTENANCE", "EMERGENCY_SHUTDOWN"
    ]

    for i in range(num_samples):
        session_id = f"SYNTH_SESSION_{i % num_sessions:02d}"
        label = int(i % num_classes)
        label_name = class_names[label]
        person_slot = "HUMAN_1" if (i % 2 == 0) else "HUMAN_2"

        # Generate smooth synthetic trajectories
        t = np.linspace(0, 2 * np.pi, sequence_length)[:, None]
        base_signal = np.sin(t + label) * 0.5
        noise = rng.normal(0, 0.05, size=(sequence_length, feature_dim)).astype(np.float32)
        features = (np.repeat(base_signal, feature_dim, axis=1) + noise).astype(np.float32)

        # Missingness mask: randomly mask 10% of features to test occlusion handling
        missingness = (rng.uniform(0, 1, size=(sequence_length, feature_dim)) > 0.1).astype(np.float32)

        sample = TemporalSequenceSample(
            sequence_id=f"SYNTH_SEQ_{i:04d}",
            person_id=person_slot,
            recording_session_id=session_id,
            activity_label=label,
            activity_name=label_name,
            features=features,
            missingness_mask=missingness,
            start_timestamp_ms=i * 1000,
            end_timestamp_ms=(i + 1) * 1000
        )
        samples.append(sample)

    return samples


def run_smoke_training(checkpoint_path: str = "checkpoints/smoke_model.pt") -> dict:
    """Executes a 2-epoch training smoke test to verify optimizer, loss, and tensor dimensions."""
    print("=" * 60)
    print("ORBITA HAR: Running Training Smoke Test (Adam Optimizer)")
    print("NOTICE: Dataset is synthetic and used strictly for software verification.")
    print("=" * 60)

    samples = generate_synthetic_dataset(num_samples=32, sequence_length=30, feature_dim=74, num_classes=6)
    train_ds, val_ds = OrbitaActivityDataset.split_by_session(samples, val_ratio=0.25)

    train_loader = DataLoader(train_ds, batch_size=8, shuffle=True)
    val_loader = DataLoader(val_ds, batch_size=8, shuffle=False)

    model = OrbitaBottleneckHAR(
        input_dim=74,
        sequence_length=30,
        bottleneck_dim_1=32,
        bottleneck_dim_2=16,
        num_classes=6,
        dropout_rate=0.2
    )

    trainer = OrbitaModelTrainer(model=model, learning_rate=0.005)

    history = []
    for epoch in range(1, 3):
        train_loss, train_acc = trainer.train_epoch(train_loader)
        val_loss, val_acc = trainer.evaluate(val_loader)
        print(f"Epoch {epoch}/2 | Train Loss: {train_loss:.4f}, Acc: {train_acc:.2%} | Val Loss: {val_loss:.4f}, Acc: {val_acc:.2%}")
        history.append({
            "epoch": epoch,
            "train_loss": train_loss,
            "train_acc": train_acc,
            "val_loss": val_loss,
            "val_acc": val_acc
        })

    trainer.save_checkpoint(checkpoint_path, epoch=2, val_acc=val_acc)
    print(f"Checkpoint successfully written to {checkpoint_path}")
    print("=" * 60)
    return {"status": "SUCCESS", "history": history, "checkpoint": checkpoint_path}


if __name__ == "__main__":
    run_smoke_training()
