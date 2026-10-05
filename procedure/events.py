"""Validate shared events and confirm only producers without confirmation metadata."""
import math
from numbers import Integral, Real

from shared.enums.module_status import ModuleStatus
from shared.schemas.activity_event import ActivityEvent
from procedure.contracts import EventPolicy


def validate_event(event: ActivityEvent, require_identity: bool) -> None:
    if not isinstance(event, ActivityEvent):
        raise ValueError("Expected shared ActivityEvent")
    for name in ("event_id", "activity_label"):
        value = getattr(event, name)
        if not isinstance(value, str) or not value.strip() or len(value) > 128:
            raise ValueError(f"Invalid {name}")
    for name in ("frame_id", "start_frame_id", "end_frame_id"):
        value = getattr(event, name)
        if isinstance(value, bool) or not isinstance(value, Integral) or value < 0:
            raise ValueError(f"Invalid {name}")
    for name in ("timestamp_s", "start_timestamp_s", "end_timestamp_s"):
        value = getattr(event, name)
        if isinstance(value, bool) or not isinstance(value, Real) or not math.isfinite(value) or value < 0:
            raise ValueError(f"Invalid {name}")
    if not event.start_frame_id <= event.frame_id <= event.end_frame_id:
        raise ValueError("frame_id must lie within the event interval")
    if not event.start_timestamp_s <= event.timestamp_s <= event.end_timestamp_s:
        raise ValueError("timestamp_s must lie within the event interval")
    value = event.confidence
    if value is not None and (isinstance(value, bool) or not isinstance(value, Real) or not math.isfinite(value) or not 0 <= value <= 1):
        raise ValueError("confidence must be None or finite in [0, 1]")
    if event.target_object_class is not None and (not isinstance(event.target_object_class, str) or not event.target_object_class.strip()):
        raise ValueError("Invalid target_object_class")
    for name in ("target_track_id", "target_object_track_id"):
        value = getattr(event, name)
        if value is not None and (isinstance(value, bool) or not isinstance(value, Integral) or value < 0):
            raise ValueError(f"Invalid {name}")
    if not isinstance(event.status, ModuleStatus) or not isinstance(event.metadata, dict):
        raise ValueError("Invalid status or metadata")
    for name in ("source_id", "session_id"):
        value = event.metadata.get(name)
        if (require_identity or value is not None) and (not isinstance(value, str) or not value.strip()):
            raise ValueError(f"metadata.{name} must be nonempty text")
    present = {"confirmed", "emitted"} & event.metadata.keys()
    if present and (len(present) != 2 or any(type(event.metadata[k]) is not bool for k in present)):
        raise ValueError("confirmed and emitted must be supplied together as booleans")
    if event.metadata.get("emitted") and not event.metadata.get("confirmed"):
        raise ValueError("An emitted event must be confirmed")


class EventGate:
    def __init__(self, policy: EventPolicy):
        self.policy = policy
        self.reset()

    def reset(self) -> None:
        self._key = self._latched = None
        self._count = 0
        self._frame = self._timestamp = None

    def accept(self, event: ActivityEvent) -> tuple[bool, str]:
        """Return (accepted, reason). Never elevate an explicit upstream rejection."""
        if event.status not in (ModuleStatus.OK, ModuleStatus.DEGRADED) or event.activity_label in self.policy.ignored_actions:
            self.reset()
            return False, "ignored_activity_or_status"
        if ((event.confidence is None and not self.policy.allow_missing_confidence)
                or (event.confidence is not None and event.confidence < self.policy.min_confidence)):
            self.reset()
            return False, "insufficient_confidence"
        if "confirmed" in event.metadata:
            self.reset()
            return (True, "upstream_confirmed") if event.metadata["confirmed"] and event.metadata["emitted"] else (False, "upstream_not_emitted")
        key = (event.activity_label, event.target_object_class, event.target_object_track_id, event.target_track_id)
        consecutive = (key == self._key and self._frame is not None
                       and event.frame_id == self._frame + 1
                       and event.timestamp_s - self._timestamp <= self.policy.max_gap_s)
        if key == self._latched and consecutive:
            self._frame, self._timestamp = event.frame_id, event.timestamp_s
            return False, "continuous_prediction_already_emitted"
        self._count = self._count + 1 if consecutive else 1
        self._key, self._frame, self._timestamp = key, event.frame_id, event.timestamp_s
        self._latched = None
        if self._count < self.policy.confirmation_frames:
            return False, "pending_confirmation"
        self._latched = key
        return True, "procedure_confirmed"
