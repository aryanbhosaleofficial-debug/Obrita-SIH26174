"""Procedure decisions only; semantic input remains shared ActivityEvent."""
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class ProcedureState(str, Enum):
    NOT_STARTED = "not_started"
    READY = "ready"
    IN_PROGRESS = "in_progress"
    RECOVERY_REQUIRED = "recovery_required"
    PAUSED = "paused"
    COMPLETED = "completed"
    ABORTED = "aborted"
    ERROR = "error"


class StepState(str, Enum):
    PENDING = "pending"
    ACTIVE = "active"
    COMPLETED = "completed"
    SKIPPED = "skipped"
    RETRY_REQUIRED = "retry_required"


class DecisionType(str, Enum):
    VALID = "valid"
    WRONG_ORDER = "wrong_order"
    SKIPPED_STEP = "skipped_step"
    REPEATED_ACTION = "repeated_action"
    UNEXPECTED_ACTION = "unexpected_action"
    IGNORED = "ignored"
    PENDING_CONFIRMATION = "pending_confirmation"
    DUPLICATE = "duplicate"
    STALE_EVENT = "stale_event"
    SESSION_MISMATCH = "session_mismatch"
    INVALID_EVENT = "invalid_event"
    COMPLETED = "completed"
    STATE_CHANGED = "state_changed"
    ERROR = "error"


class RecoveryAction(str, Enum):
    CONTINUE = "continue"
    RETRY_CURRENT_STEP = "retry_current_step"
    PERFORM_MISSING_STEP = "perform_missing_step"
    IGNORE = "ignore"
    PAUSE = "pause"
    RESTART_REQUIRED = "restart_required"
    MANUAL_REVIEW = "manual_review"


class GuidanceSeverity(str, Enum):
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"


@dataclass(frozen=True)
class RecoveryRule:
    action: RecoveryAction
    message: str | None = None


@dataclass(frozen=True)
class EventPolicy:
    min_confidence: float = 0.55
    allow_missing_confidence: bool = False
    confirmation_frames: int = 3
    max_gap_s: float = 1.0
    require_identity: bool = True
    ignored_actions: tuple[str, ...] = ("unknown", "NONE", "UNCERTAIN", "idle")
    alert_cooldown_s: float = 5.0
    history_limit: int = 256
    dedup_limit: int = 2048


@dataclass(frozen=True)
class StepProgress:
    step_id: str
    instruction: str
    state: StepState


@dataclass(frozen=True)
class GuidanceDecision:
    decision: DecisionType
    procedure_id: str
    procedure_state: ProcedureState
    current_step_id: str | None
    current_step_index: int | None
    observed_action: str | None
    expected_action: str | None
    expected_step_id: str | None
    next_step_id: str | None
    next_instruction: str | None
    recovery_action: RecoveryAction | None
    message: str
    severity: GuidanceSeverity
    timestamp_s: float | None
    frame_id: int | None
    event_id: str | None
    source_id: str | None
    session_id: str | None
    confidence: float | None
    completed_steps: tuple[str, ...]
    skipped_steps: tuple[str, ...]
    matching_step_id: str | None
    step_states: tuple[StepProgress, ...]
    should_display: bool
    should_speak: bool
    dedupe_key: str
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ProcedureHistoryEntry:
    event_id: str | None
    timestamp_s: float | None
    decision: DecisionType
    step_before: str | None
    step_after: str | None
    message: str


@dataclass(frozen=True)
class ProcedureSnapshot:
    procedure_id: str
    state: ProcedureState
    current_step_index: int | None
    current_step_id: str | None
    completed_steps: tuple[str, ...]
    step_states: tuple[StepProgress, ...]
    source_id: str | None
    session_id: str | None
    last_valid_action: str | None
    last_event_id: str | None
    timestamp_s: float | None
    recovery_action: RecoveryAction | None
