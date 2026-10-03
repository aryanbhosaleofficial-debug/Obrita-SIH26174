"""Bottleneck -> ReLU -> Bottleneck PyTorch architecture for HAR."""

from typing import Dict, Optional, Tuple
import torch
import torch.nn as nn
import torch.nn.functional as F

from ..schemas.feature_types import FEATURE_SCHEMA_VERSION


class OrbitaBottleneckHAR(nn.Module):
    """Activity Recognition Model with explicit Bottleneck -> ReLU -> Bottleneck structure.
    
    ARCHITECTURAL SPECIFICATION & CLARIFICATION (Task 4 Requirement):
    -----------------------------------------------------------------
    1. Distinction between Model and Optimizer:
       - The Neural Network Architecture defines the mathematical hypothesis space
         (parameters W, b, layers, and non-linearities) mapping kinematic sequences
         X ∈ R^(B × T × D) to class logits Y ∈ R^(B × C).
       - The Adam Optimizer (Adaptive Moment Estimation) is an external iterative
         first-order optimization algorithm that maintains exponentially decaying
         moving averages of past gradients (m_t) and past squared gradients (v_t)
         to update model parameters during training. It is NOT part of the forward
         model graph.
         
    2. Explicit Layer Structure:
       - Input Dimension (D): 74 features (coordinates, velocities, angles, distances, orientation).
       - Temporal Aggregation: Dual Mean + Max pooling across temporal window T.
       - Projection Layer: Linear(D * 2 -> input_dim).
       - First Bottleneck (Linear): Compresses from input_dim to bottleneck_dim_1 (e.g., 74 -> 32).
       - Non-Linear Activation: ReLU(x) = max(0, x).
       - Regularization: Dropout(p=dropout_rate).
       - Second Bottleneck (Linear): Further compresses from bottleneck_dim_1 to bottleneck_dim_2 (e.g., 32 -> 16).
       - Final Classification Head (Linear): Projects from bottleneck_dim_2 to num_classes (e.g., 16 -> 6).
    """

    def __init__(
        self,
        input_dim: int = 74,
        sequence_length: int = 30,
        bottleneck_dim_1: int = 32,
        bottleneck_dim_2: int = 16,
        num_classes: int = 6,
        dropout_rate: float = 0.25,
        feature_schema_version: str = FEATURE_SCHEMA_VERSION
    ):
        super().__init__()
        self.input_dim = input_dim
        self.sequence_length = sequence_length
        self.bottleneck_dim_1 = bottleneck_dim_1
        self.bottleneck_dim_2 = bottleneck_dim_2
        self.num_classes = num_classes
        self.dropout_rate = dropout_rate
        self.feature_schema_version = feature_schema_version
        if self.feature_schema_version != FEATURE_SCHEMA_VERSION:
            raise ValueError(
                f"Unsupported feature schema {self.feature_schema_version}; "
                f"expected {FEATURE_SCHEMA_VERSION}"
            )
        if input_dim <= 0 or sequence_length <= 0:
            raise ValueError("input_dim and sequence_length must be positive")

        # Temporal representation: projects concatenated mean and max sequence pools
        self.input_projection = nn.Linear(input_dim * 2, input_dim)
        self.input_norm = nn.LayerNorm(input_dim)

        # Primary Bottleneck Layer 1: input_dim -> bottleneck_dim_1
        self.bottleneck_1 = nn.Linear(input_dim, bottleneck_dim_1)
        
        # Explicit Non-linear Activation
        self.activation = nn.ReLU()
        
        # Regularization Dropout
        self.dropout = nn.Dropout(p=dropout_rate)
        
        # Secondary Bottleneck Layer 2: bottleneck_dim_1 -> bottleneck_dim_2
        self.bottleneck_2 = nn.Linear(bottleneck_dim_1, bottleneck_dim_2)
        
        # Final Classification Head: bottleneck_dim_2 -> num_classes
        self.classifier = nn.Linear(bottleneck_dim_2, num_classes)

    def forward(
        self,
        x: torch.Tensor,
        mask: Optional[torch.Tensor] = None
    ) -> Tuple[torch.Tensor, torch.Tensor]:
        """Forward pass.
        
        Args:
            x: Tensor of shape (B, T, D) or (B, D).
            mask: Optional missingness mask of shape matching x (1=valid, 0=missing).
            
        Returns:
            Tuple of (logits [B, C], bottleneck_embedding [B, bottleneck_dim_2])
        """
        # If input has missingness mask, apply masking to zero-out occluded dimensions
        if mask is not None:
            if mask.shape != x.shape:
                raise ValueError(f"mask shape {mask.shape} must match input shape {x.shape}")
            x = x * mask

        # Handle 3D sequence (B, T, D) or 2D frame (B, D)
        if x.dim() == 3:
            B, T, D = x.shape
            if T != self.sequence_length:
                raise ValueError(
                    f"expected sequence length {self.sequence_length}, got {T}"
                )
            if D != self.input_dim:
                raise ValueError(f"expected feature dimension {self.input_dim}, got {D}")
            # Dual temporal pooling: Average along time + Max along time
            t_mean = torch.mean(x, dim=1)           # (B, D)
            t_max, _ = torch.max(x, dim=1)          # (B, D)
            pooled = torch.cat([t_mean, t_max], dim=-1) # (B, D * 2)
            h = self.input_projection(pooled)       # (B, D)
        elif x.dim() == 2:
            if x.shape[1] != self.input_dim:
                raise ValueError(f"expected feature dimension {self.input_dim}, got {x.shape[1]}")
            # Replicate if single frame passed
            pooled = torch.cat([x, x], dim=-1)
            h = self.input_projection(pooled)
        else:
            raise ValueError(f"Expected 2D or 3D tensor, got shape {x.shape}")

        h = self.input_norm(h)

        # --- EXPLICIT BOTTLENECK 1 ---
        h_b1 = self.bottleneck_1(h)           # (B, bottleneck_dim_1)

        # --- EXPLICIT ReLU ACTIVATION ---
        h_act = self.activation(h_b1)        # (B, bottleneck_dim_1)
        h_drop = self.dropout(h_act)

        # --- EXPLICIT BOTTLENECK 2 ---
        h_b2 = self.bottleneck_2(h_drop)      # (B, bottleneck_dim_2)

        # --- CLASSIFICATION HEAD ---
        logits = self.classifier(h_b2)       # (B, num_classes)

        return logits, h_b2
