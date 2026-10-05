"""Image validation plus the preserved Module 03 receiving contract."""

import math
from dataclasses import dataclass
from numbers import Integral, Real
from typing import Any

import numpy as np

from .contract_validator import BoundaryInputError, validate_boundary_input


@dataclass(frozen=True)
class ValidatedInput:
    frame: np.ndarray | None
    frame_id: int | None
    timestamp: float | None
    hand_data: Any = None
    valid: bool = False
    reason: str = "invalid frame"


def validate_input(
    frame: Any, frame_id: Any, timestamp: Any, hand_data: Any = None
) -> ValidatedInput:
    """Borrow validated pixels read-only; only ROI preprocessing copies pixels."""
    if not isinstance(frame, np.ndarray) or frame.size == 0:
        return ValidatedInput(
            None, None, None, hand_data, False, "frame must be a nonempty ndarray"
        )
    if (
        frame.dtype != np.uint8
        or frame.ndim not in (2, 3)
        or (frame.ndim == 3 and frame.shape[2] != 3)
    ):
        return ValidatedInput(
            None,
            None,
            None,
            hand_data,
            False,
            "frame must be uint8 grayscale or three-channel BGR",
        )
    if isinstance(frame_id, bool) or not isinstance(frame_id, Integral) or frame_id < 0:
        return ValidatedInput(
            None, None, None, hand_data, False, "frame_id must be a nonnegative integer"
        )
    if (
        isinstance(timestamp, bool)
        or not isinstance(timestamp, Real)
        or not math.isfinite(timestamp)
        or timestamp < 0
    ):
        return ValidatedInput(
            None,
            None,
            None,
            hand_data,
            False,
            "timestamp must be finite nonnegative source seconds",
        )
    try:
        hands = (
            hand_data
            if isinstance(hand_data, (list, tuple))
            else [hand_data]
            if hand_data is not None
            else []
        )
        for hand in hands:
            coords = (
                hand.get("point", hand.get("landmarks", hand.get("coordinates")))
                if isinstance(hand, dict)
                else hand
            )
            if coords is None:
                continue
            points = np.asarray(coords, dtype=float).reshape(-1, 2)
            if not np.isfinite(points).all():
                raise ValueError("nonfinite hand coordinates")
    except (TypeError, ValueError):
        return ValidatedInput(
            None,
            None,
            None,
            hand_data,
            False,
            "hand_data must contain finite pixel XY coordinates",
        )
    return ValidatedInput(frame, int(frame_id), float(timestamp), hand_data, True, "")


def process(
    frame: Any, frame_id: Any, timestamp: Any, hand_data: Any = None
) -> dict[str, Any]:
    result = validate_input(frame, frame_id, timestamp, hand_data)
    return {
        "valid": result.valid,
        "frame": result.frame,
        "frame_id": result.frame_id,
        "timestamp": result.timestamp,
        "hand_data": result.hand_data,
        "reason": result.reason,
    }


__all__ = [
    "BoundaryInputError",
    "ValidatedInput",
    "process",
    "validate_boundary_input",
    "validate_input",
]
