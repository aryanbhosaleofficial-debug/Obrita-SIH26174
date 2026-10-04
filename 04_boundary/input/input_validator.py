"""
Input validation for Module 04.

Implementation status:
    Scaffold only.

Input:
    Synchronized packet pair

Output:
    Validated pair or rejection reason

Owner:
    Module 04 — Boundary Detection
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np


@dataclass(frozen=True)
class ValidatedInput:
    frame: np.ndarray | None
    frame_id: int | None
    timestamp: float | None
    hand_data: Any = None
    valid: bool = False
    reason: str = "invalid frame"


def validate_input(frame: Any, frame_id: Any, timestamp: Any, hand_data: Any = None) -> ValidatedInput:
    if frame is None:
        return ValidatedInput(None, None, None, hand_data, False, "frame is missing")
    try:
        array = np.asarray(frame)
    except Exception:
        return ValidatedInput(None, None, None, hand_data, False, "frame is not array-like")
    if array.size == 0 or array.ndim not in (2, 3):
        return ValidatedInput(None, None, None, hand_data, False, "frame is empty or invalid")
    try:
        fid, ts = int(frame_id), float(timestamp)
    except (TypeError, ValueError):
        return ValidatedInput(None, None, None, hand_data, False, "metadata is invalid")
    return ValidatedInput(array.copy(), fid, ts, hand_data, True, "")


def process(frame: Any, frame_id: Any, timestamp: Any, hand_data: Any = None) -> dict[str, Any]:
    result = validate_input(frame, frame_id, timestamp, hand_data)
    return {"valid": result.valid, "frame": result.frame, "frame_id": result.frame_id,
            "timestamp": result.timestamp, "hand_data": result.hand_data, "reason": result.reason}
