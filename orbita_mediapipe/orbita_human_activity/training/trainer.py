"""Training engine using Adam optimizer for the Bottleneck HAR architecture."""

import os
from typing import Dict, Optional, Tuple
import torch
import torch.nn as nn
from torch.utils.data import DataLoader

from ..models.bottleneck_network import OrbitaBottleneckHAR
from ..schemas.feature_types import FEATURE_SCHEMA_VERSION
from .dataset import OrbitaActivityDataset


class OrbitaModelTrainer:
    """Trains the OrbitaBottleneckHAR network using the Adam optimizer.
    
    DISTINCTION (Task 4 Requirement):
    - OrbitaBottleneckHAR: The static structural neural network graph.
    - Adam (Optimizer): The first-order gradient-based optimization algorithm
      configured with learning rate, beta moments, and weight decay to update
      model parameters.
    """

    def __init__(
        self,
        model: OrbitaBottleneckHAR,
        learning_rate: float = 0.001,
        weight_decay: float = 0.0001,
        betas: Tuple[float, float] = (0.9, 0.999),
        eps: float = 1e-8,
        device: Optional[str] = None
    ):
        self.device = device or ("cuda" if torch.cuda.is_available() else "cpu")
        self.model = model.to(self.device)

        # Explicit Adam Optimizer initialization
        self.optimizer = torch.optim.Adam(
            self.model.parameters(),
            lr=learning_rate,
            betas=betas,
            eps=eps,
            weight_decay=weight_decay
        )
        
        # Loss function
        self.criterion = nn.CrossEntropyLoss()

    def train_epoch(self, dataloader: DataLoader) -> Tuple[float, float]:
        """Runs one training epoch."""
        self.model.train()
        total_loss = 0.0
        correct = 0
        total = 0

        for x, mask, y in dataloader:
            x, mask, y = x.to(self.device), mask.to(self.device), y.to(self.device)

            self.optimizer.zero_grad()
            logits, _ = self.model(x, mask)
            loss = self.criterion(logits, y)
            loss.backward()
            self.optimizer.step()

            total_loss += float(loss.item()) * len(y)
            preds = torch.argmax(logits, dim=-1)
            correct += int((preds == y).sum().item())
            total += len(y)

        avg_loss = total_loss / max(total, 1)
        accuracy = correct / max(total, 1)
        return avg_loss, accuracy

    def evaluate(self, dataloader: DataLoader) -> Tuple[float, float]:
        """Evaluates model on validation data."""
        self.model.eval()
        total_loss = 0.0
        correct = 0
        total = 0

        with torch.no_grad():
            for x, mask, y in dataloader:
                x, mask, y = x.to(self.device), mask.to(self.device), y.to(self.device)
                logits, _ = self.model(x, mask)
                loss = self.criterion(logits, y)

                total_loss += float(loss.item()) * len(y)
                preds = torch.argmax(logits, dim=-1)
                correct += int((preds == y).sum().item())
                total += len(y)

        avg_loss = total_loss / max(total, 1)
        accuracy = correct / max(total, 1)
        return avg_loss, accuracy

    def save_checkpoint(self, filepath: str, epoch: int, val_acc: float):
        """Saves model weights, optimizer state, and training metadata."""
        os.makedirs(os.path.dirname(os.path.abspath(filepath)), exist_ok=True)
        torch.save({
            "epoch": epoch,
            "val_accuracy": val_acc,
            "feature_schema_version": FEATURE_SCHEMA_VERSION,
            "architecture": "OrbitaBottleneckHAR",
            "optimizer": "Adam",
            "model_state_dict": self.model.state_dict(),
            "optimizer_state_dict": self.optimizer.state_dict(),
            "model_config": {
                "input_dim": self.model.input_dim,
                "sequence_length": self.model.sequence_length,
                "bottleneck_dim_1": self.model.bottleneck_dim_1,
                "bottleneck_dim_2": self.model.bottleneck_dim_2,
                "num_classes": self.model.num_classes,
                "dropout_rate": self.model.dropout_rate,
                "feature_schema_version": self.model.feature_schema_version
            },
            "optimizer_config": {
                "learning_rate": self.optimizer.param_groups[0]["lr"],
                "betas": self.optimizer.param_groups[0]["betas"],
                "eps": self.optimizer.param_groups[0]["eps"],
                "weight_decay": self.optimizer.param_groups[0]["weight_decay"],
            }
        }, filepath)

    def load_checkpoint(self, filepath: str, strict: bool = True) -> dict:
        """Load a checkpoint only when its model/schema contract matches."""
        checkpoint = torch.load(filepath, map_location=self.device, weights_only=False)
        if checkpoint.get("architecture") != "OrbitaBottleneckHAR":
            raise ValueError("Checkpoint architecture is missing or incompatible")
        if checkpoint.get("feature_schema_version") != FEATURE_SCHEMA_VERSION:
            raise ValueError("Checkpoint feature schema version is incompatible")
        config = checkpoint.get("model_config", {})
        expected = {
            "input_dim": self.model.input_dim,
            "sequence_length": self.model.sequence_length,
            "bottleneck_dim_1": self.model.bottleneck_dim_1,
            "bottleneck_dim_2": self.model.bottleneck_dim_2,
            "num_classes": self.model.num_classes,
            "dropout_rate": self.model.dropout_rate,
            "feature_schema_version": self.model.feature_schema_version,
        }
        for key, value in expected.items():
            if config.get(key) != value:
                raise ValueError(f"Checkpoint model configuration mismatch for {key}")
        self.model.load_state_dict(checkpoint["model_state_dict"], strict=strict)
        if "optimizer_state_dict" in checkpoint:
            self.optimizer.load_state_dict(checkpoint["optimizer_state_dict"])
        return checkpoint
