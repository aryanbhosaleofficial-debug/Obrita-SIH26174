"""
ActivityEvent — a confirmed human activity.

Originating module: Module 05 — Perception Fusion
Consuming module:   Procedure FSM (procedure/)

The event describes WHAT the operator did. Whether it was the correct,
wrong-order or skipped step is decided by the Procedure FSM, not here.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from shared.enums.module_status import ModuleStatus


@dataclass
class ActivityEvent:
    # Required ---------------------------------------------------------------
    event_id: str
    # Unique within a session.

    activity_label: str
    # From the configured activity label set; must match `expected_activity`
    # values used in procedures/*.yaml.

    frame_id: int
    timestamp_s: float
    # Frame / time at which the activity was confirmed.

    start_frame_id: int
    end_frame_id: int
    start_timestamp_s: float
    end_timestamp_s: float

    # Optional ---------------------------------------------------------------
    target_track_id: Optional[int] = None
    # Operator track_id.

    target_object_track_id: Optional[int] = None
    target_object_class: Optional[str] = None

    confidence: Optional[float] = None
    # Fused confidence in [0.0, 1.0]; None means unavailable, never assumed 1.0.

    evidence_summary: dict[str, float] = field(default_factory=dict)
    # Evidence source name -> contribution, e.g. {"gesture": ..., "contact": ...}.

    conflicts: list[str] = field(default_factory=list)
    # Human-readable description of evidence conflicts that were resolved.

    status: ModuleStatus = ModuleStatus.OK
    metadata: dict = field(default_factory=dict)
    # Session/source identity, rule, confirmation state and emission flag.
