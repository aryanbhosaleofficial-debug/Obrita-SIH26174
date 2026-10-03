"""Unit tests for the Bottleneck -> ReLU -> Bottleneck PyTorch architecture."""

import unittest
import torch
import torch.nn as nn

from orbita_human_activity.models.bottleneck_network import OrbitaBottleneckHAR


class TestModelArchitecture(unittest.TestCase):

    def setUp(self):
        self.B = 4
        self.T = 30
        self.D = 74
        self.C = 6
        self.b1 = 32
        self.b2 = 16
        self.model = OrbitaBottleneckHAR(
            input_dim=self.D,
            sequence_length=self.T,
            bottleneck_dim_1=self.b1,
            bottleneck_dim_2=self.b2,
            num_classes=self.C,
            dropout_rate=0.2
        )

    def test_forward_shape_sequence(self):
        """Verifies forward pass with 3D sequence input (B, T, D)."""
        x = torch.randn(self.B, self.T, self.D)
        mask = torch.ones(self.B, self.T, self.D)
        logits, emb = self.model(x, mask)

        self.assertEqual(logits.shape, (self.B, self.C))
        self.assertEqual(emb.shape, (self.B, self.b2))

    def test_forward_shape_single_frame(self):
        """Verifies forward pass with 2D single-frame input (B, D)."""
        x = torch.randn(self.B, self.D)
        logits, emb = self.model(x)

        self.assertEqual(logits.shape, (self.B, self.C))
        self.assertEqual(emb.shape, (self.B, self.b2))

    def test_loss_and_backward(self):
        """Verifies gradient flow through both bottleneck layers and classification head."""
        x = torch.randn(self.B, self.T, self.D)
        y = torch.tensor([0, 1, 2, 3], dtype=torch.long)
        criterion = nn.CrossEntropyLoss()

        self.model.zero_grad()
        logits, _ = self.model(x)
        loss = criterion(logits, y)
        loss.backward()

        # Check gradients exist on all key layers
        self.assertIsNotNone(self.model.bottleneck_1.weight.grad)
        self.assertIsNotNone(self.model.bottleneck_2.weight.grad)
        self.assertIsNotNone(self.model.classifier.weight.grad)
        self.assertFalse(torch.isnan(loss).item())


if __name__ == "__main__":
    unittest.main()
