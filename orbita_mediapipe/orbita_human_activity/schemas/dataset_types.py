"""Dataset sample and model inference prediction schemas."""

from dataclasses import dataclass, field
from typing import Dict, List, Optional
import numpy as np


@dataclass
class TemporalSequenceSample:
    """A fixed-length temporal window sequence for training and inference.
    
    Guarantees no temporal leakage across splits by attaching recording_session_id.
    """
    sequence_id: str
    person_id: str
    recording_session_id: str
    activity_label: int
    activity_name: str
    features: np.ndarray        # Shape: (T, D) float32
    missingness_mask: np.ndarray# Shape: (T, D) float32
    start_timestamp_ms: int
    end_timestamp_ms: int
    frame_ids: List[int] = field(default_factory=list)
    timestamps_ms: List[int] = field(default_factory=list)
    coordinate_space: str = "UNKNOWN"
    measurement_statuses: List[str] = field(default_factory=list)
    human_label: Optional[str] = None

    @property
    def feature_schema_version(self) -> str:
        from .feature_types import FEATURE_SCHEMA_VERSION
        return FEATURE_SCHEMA_VERSION

    @property
    def sequence_length(self) -> int:
        return self.features.shape[0]

    @property
    def feature_dim(self) -> int:
        return self.features.shape[1]


@dataclass
class PredictionResult:
    """Inference output from Bottleneck activity recognition model."""
    timestamp_ms: int
    person_id: str
    predicted_class_id: int
    predicted_class_name: str
    confidence: float
    probabilities: Dict[str, float] = field(default_factory=dict)
    is_reliable: bool = True
    notes: Optional[str] = None

    def to_dict(self) -> Dict:
        return {
            "timestamp_ms": self.timestamp_ms,
            "person_id": self.person_id,
            "predicted_class_id": self.predicted_class_id,
            "predicted_class_name": self.predicted_class_name,
            "confidence": round(float(self.confidence), 4),
            "probabilities": {k: round(float(v), 4) for k, v in self.probabilities.items()},
            "is_reliable": self.is_reliable,
            "notes": self.notes
        }
