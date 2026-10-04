"""Machine-readable diagnostics shared by every stage; notices do not degrade status."""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class NoticeCode(str, Enum):
    OBJECT_TRACKING_DISABLED = "object_tracking_disabled"
    OBJECT_IDENTITY_UNAVAILABLE = "object_identity_unavailable"
    HAND_CONFIDENCE_UNAVAILABLE = "hand_confidence_unavailable"
    HAND_IDENTITY_NONPERSISTENT = "hand_identity_nonpersistent"
    STATIC_REFERENCE = "static_reference"
    REFERENCE_DISABLED = "reference_disabled"
    DETECTOR_DISABLED = "detector_disabled"
    HAND_TRACKER_DISABLED = "hand_tracker_disabled"
    AMBIGUOUS_ASSOCIATION = "ambiguous_association"


class WarningCode(str, Enum):
    INVALID_FRAME = "invalid_frame"
    SOURCE_CHANGED = "source_changed"
    NON_MONOTONIC_FRAME = "non_monotonic_frame"
    SOURCE_FRAME_MISSING = "source_frame_missing"
    TEMPORAL_HISTORY_RESET = "temporal_history_reset"
    DETECTOR_FAILURE = "detector_failure"
    HAND_TRACKER_FAILURE = "hand_tracker_failure"
    POSE_TRACKER_FAILURE = "pose_tracker_failure"
    REFERENCE_FRAME_UNAVAILABLE = "reference_frame_unavailable"
    REFERENCE_FRAME_FAILURE = "reference_frame_failure"
    INVALID_OBSERVATION = "invalid_observation"
    CPU_FALLBACK = "cpu_fallback"
    GEOMETRY_FAILURE = "geometry_failure"
    UPSTREAM_FAILURE = "upstream_failure"


@dataclass(frozen=True)
class Diagnostic:
    code: NoticeCode | WarningCode
    details: dict[str, Any] = field(default_factory=dict)


def diagnostic_status(warnings: list[Diagnostic], *, failed: bool = False):
    from shared.enums.module_status import ModuleStatus

    if failed:
        return ModuleStatus.ERROR
    return ModuleStatus.DEGRADED if warnings else ModuleStatus.OK
