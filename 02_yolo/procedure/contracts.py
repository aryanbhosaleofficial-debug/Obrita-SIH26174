"""Immutable procedure and action side outputs, independent of SIH schemas."""

from dataclasses import dataclass


@dataclass(frozen=True)
class ProcedureStep:
    index: int
    step_id: str
    action: str
    object_name: str | None
    instruction: str
    warning: str
    confirmation_frames: int
    timeout_ms: int | None = None


@dataclass(frozen=True)
class ProcedureDefinition:
    name: str
    steps: tuple[ProcedureStep, ...]


@dataclass(frozen=True)
class FastActionResult:
    action: str
    object_name: str | None
    frame_id: int
    timestamp_s: float
    evidence: str


@dataclass(frozen=True)
class ConfirmedAction:
    action: str
    object_name: str | None
    frame_id: int
    timestamp_s: float
    source: str
    confirmed_monotonic_s: float


@dataclass(frozen=True)
class ProcedureState:
    current_step_index: int
    total_steps: int
    completed_steps: tuple[str, ...]
    last_action: str
    status: str
    next_step_id: str | None
    next_action: str | None
    next_instruction: str | None


@dataclass(frozen=True)
class ProcedureEvent:
    event: str
    expected: str | None
    observed: str
    step_id: str | None
    frame_id: int
    timestamp_s: float
    confirmed_monotonic_s: float
    skipped_steps: tuple[str, ...] = ()
