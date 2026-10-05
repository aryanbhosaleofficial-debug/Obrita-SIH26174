"""Deterministic procedure authority over shared semantic ActivityEvent packets."""
from collections import deque
from copy import deepcopy
from enum import Enum
import logging

from shared.schemas.activity_event import ActivityEvent
from procedure.contracts import (DecisionType as D, GuidanceDecision, GuidanceSeverity as Severity,
    ProcedureHistoryEntry, ProcedureSnapshot, ProcedureState as State, RecoveryAction as Recovery,
    StepProgress, StepState)
from procedure.events import EventGate, validate_event
from procedure.procedure_loader import ProcedureDefinition, definition_from_steps, validate_definition
from procedure.recovery import recovery_message, recovery_rule
from procedure.step_validator import matches

LOGGER = logging.getLogger(__name__)
BLOCKING = {Recovery.PAUSE, Recovery.MANUAL_REVIEW, Recovery.RESTART_REQUIRED}


class StepOutcome(str, Enum):
    """Historical on_event return values; process() exposes richer decisions."""
    CORRECT = "correct"
    WRONG_ORDER = "wrong_order"
    SKIPPED = "skipped"
    UNRELATED = "unrelated"
    COMPLETED = "completed"


class ProcedureFSM:
    """Single synchronous procedure owner; callers serialize events and controls."""
    def __init__(self, steps=None, *, definition: ProcedureDefinition | None = None):
        if steps is not None and definition is not None:
            raise ValueError("Provide definition or legacy steps, not both")
        self.definition = validate_definition(definition) if definition is not None else definition_from_steps(steps or [])
        self.policy = self.definition.event_policy
        self.gate = EventGate(self.policy)
        self._revision = 0
        self._initialize()
        if definition is None:  # preserve historical constructor/on_event workflow
            self.start()

    def _initialize(self):
        self.state = State.NOT_STARTED
        self._current_index = 0
        self._completed = []
        self._states = [StepState.PENDING] * len(self.definition.steps)
        self._history = deque(maxlen=self.policy.history_limit)
        self._seen_order = deque()
        self._seen = set()
        self._stream = None
        self._last_frame = self._last_timestamp = None
        self.last_event = self.last_confirmed_event = None
        self.last_valid_action = None
        self._recovery = None
        self._alerts = {}
        self._revision += 1
        self.gate.reset()

    @property
    def current_index(self):
        return self._current_index

    @property
    def steps(self):
        return tuple(s.as_dict() for s in self.definition.steps)

    @property
    def completed_steps(self):
        return list(self._completed) if isinstance(self._completed, list) else []

    @property
    def history(self):
        return tuple(self._history)

    @property
    def expected(self):
        index = self._current_index
        return self.definition.steps[index] if type(index) is int and 0 <= index < len(self.definition.steps) else None

    def current_step(self):
        return self.expected.as_dict() if self.expected else None

    def _progress(self):
        if not isinstance(self._states, list) or not all(isinstance(s, StepState) for s in self._states):
            return ()  # ERROR output must not publish corrupt step statuses as facts
        return tuple(StepProgress(s.id, s.description, status)
                     for s, status in zip(self.definition.steps, self._states))

    def snapshot(self) -> ProcedureSnapshot:
        """Detached read-only in-memory view; no unsafe checkpoint restore API."""
        step = self.expected
        return ProcedureSnapshot(self.definition.experiment_id, self.state,
            self._current_index if step else None, step.id if step else None,
            tuple(self._completed), self._progress(), *(self._stream or (None, None)),
            self.last_valid_action, self.last_event.event_id if self.last_event else None,
            self._last_timestamp, self._recovery)

    def start(self, *, source_id: str | None = None, session_id: str | None = None) -> GuidanceDecision:
        if self.state != State.NOT_STARTED:
            raise ValueError("reset() is required before starting another run")
        if (source_id is None) != (session_id is None) or any(v is not None and (not isinstance(v, str) or not v.strip()) for v in (source_id, session_id)):
            raise ValueError("Supply both nonempty source_id and session_id, or neither")
        self._stream = (source_id, session_id) if source_id is not None else None
        self.state = State.READY
        self._states[0] = StepState.ACTIVE
        self._revision += 1
        return self._make(D.STATE_CHANGED, f"Start: {self.expected.description}", speak=True)

    def reset(self) -> GuidanceDecision:
        self._initialize()
        return self._make(D.STATE_CHANGED, "Procedure reset. Start a new run.", record=False)

    def pause(self) -> GuidanceDecision:
        if self.state not in (State.READY, State.IN_PROGRESS, State.RECOVERY_REQUIRED):
            raise ValueError("Only an active procedure can pause")
        self.state = State.PAUSED
        self.gate.reset()
        self._revision += 1
        return self._make(D.STATE_CHANGED, "Procedure paused.", speak=True)

    def resume(self) -> GuidanceDecision:
        """Explicit operator acknowledgment; never completes or reverses a step."""
        if self.state not in (State.PAUSED, State.RECOVERY_REQUIRED):
            raise ValueError("Only a paused/recovering procedure can resume")
        if self._recovery == Recovery.RESTART_REQUIRED:
            raise ValueError("Recovery requires reset() and start()")
        self._clear_recovery()
        self.state = State.IN_PROGRESS if self._completed else State.READY
        self.gate.reset()
        self._revision += 1
        return self._make(D.STATE_CHANGED, f"Resume: {self.expected.description}", speak=True)

    def abort(self) -> GuidanceDecision:
        if self.state in (State.COMPLETED, State.ABORTED):
            raise ValueError("Procedure is already terminal")
        self.state = State.ABORTED
        self.gate.reset()
        self._revision += 1
        return self._make(D.STATE_CHANGED, "Procedure aborted. Verify the setup before restarting.", speak=True)

    def _clear_recovery(self):
        self._recovery = None
        for index in range(self._current_index, len(self._states)):
            self._states[index] = StepState.ACTIVE if index == self._current_index else StepState.PENDING

    def _integrity_ok(self):
        return (isinstance(self.state, State) and type(self._current_index) is int
                and 0 <= self._current_index <= len(self.definition.steps)
                and isinstance(self._states, list) and isinstance(self._completed, list)
                and len(self._states) == len(self.definition.steps)
                and all(isinstance(s, StepState) for s in self._states)
                and self._completed == [s.id for s, status in zip(self.definition.steps, self._states) if status == StepState.COMPLETED]
                and all(s in (StepState.COMPLETED, StepState.SKIPPED) for s in self._states[:self._current_index])
                and all(s not in (StepState.COMPLETED, StepState.SKIPPED) for s in self._states[self._current_index:])
                and (self.state != State.COMPLETED or self._current_index == len(self._states))
                and (self._current_index < len(self._states) or self.state in (State.COMPLETED, State.ABORTED, State.ERROR)))

    def _remember(self, event_id):
        if len(self._seen_order) == self.policy.dedup_limit:
            self._seen.remove(self._seen_order.popleft())
        self._seen_order.append(event_id)
        self._seen.add(event_id)

    def process(self, event: ActivityEvent | None) -> GuidanceDecision:
        """Consume one semantic event. Invalid/stale/duplicate packets never advance."""
        if not self._integrity_ok():
            self.state = State.ERROR
            self.gate.reset()
            return self._make(D.ERROR, "Procedure state inconsistent. Reset and verify the procedure.", severity=Severity.ERROR, speak=True, details={"state_corrupt": True})
        try:
            validate_event(event, self.policy.require_identity)
        except ValueError as exc:
            self.gate.reset()
            return self._make(D.INVALID_EVENT, str(exc), display=False, details={"reason": str(exc)})
        event = deepcopy(event)  # callers cannot mutate retained evidence/history later
        stream = (event.metadata.get("source_id"), event.metadata.get("session_id"))
        if self._stream is not None and stream != self._stream:
            self.gate.reset()
            return self._make(D.SESSION_MISMATCH, "Source/session changed. Reset before starting the new session.", event, severity=Severity.WARNING, speak=True)
        if event.metadata.get("procedure_id", self.definition.experiment_id) != self.definition.experiment_id:
            self.gate.reset()
            return self._make(D.SESSION_MISMATCH, "Event belongs to another procedure.", event, severity=Severity.WARNING, speak=True)
        if event.event_id in self._seen:
            return self._make(D.DUPLICATE, "Duplicate event ignored.", event, display=False)
        if self._last_frame is not None and (event.frame_id <= self._last_frame or event.timestamp_s <= self._last_timestamp):
            return self._make(D.STALE_EVENT, "Out-of-order event ignored.", event, display=False)
        if self.state == State.NOT_STARTED:
            self.gate.reset()
            return self._make(D.IGNORED, "Start the procedure before accepting events.", event, display=False)
        self._stream = stream
        self._last_frame, self._last_timestamp = event.frame_id, event.timestamp_s
        self.last_event = event
        self._remember(event.event_id)
        if self.state in (State.COMPLETED, State.ABORTED, State.ERROR, State.PAUSED):
            self.gate.reset()
            outcome = D.COMPLETED if self.state == State.COMPLETED else D.IGNORED
            return self._make(outcome, "Procedure complete." if outcome == D.COMPLETED else f"Procedure {self.state.value}.", event, display=False)
        accepted, reason = self.gate.accept(event)
        if not accepted:
            outcome = D.PENDING_CONFIRMATION if reason in ("pending_confirmation", "upstream_not_emitted") else D.IGNORED
            return self._make(outcome, "Waiting for confirmed activity.", event, display=False, details={"reason": reason})
        self.last_confirmed_event = event
        before = self.expected
        if self._recovery in BLOCKING:
            return self._make(D.IGNORED, "Operator verification is required before resuming.", event, before=before, display=False)
        match = next((i for i, step in enumerate(self.definition.steps) if matches(event, step)), None)
        if match == self._current_index:
            return self._advance(event, before)
        if match is not None and match > self._current_index:
            skipped = tuple(s.id for s in self.definition.steps[self._current_index:match])
            if all(s.optional for s in self.definition.steps[self._current_index:match]):
                for index in range(self._current_index, match):
                    self._states[index] = StepState.SKIPPED
                self._current_index = match
                return self._advance(event, before, skipped)
            outcome = D.WRONG_ORDER if self._current_index == 0 else D.SKIPPED_STEP
            return self._recover(outcome, event, before, match, skipped)
        if match is not None and self._states[match] == StepState.COMPLETED:
            return self._recover(D.REPEATED_ACTION, event, before, match)
        return self._recover(D.UNEXPECTED_ACTION, event, before, match)

    def _advance(self, event, before, skipped=()):
        step = self.expected
        self._states[self._current_index] = StepState.COMPLETED
        self._completed.append(step.id)
        self._current_index += 1
        self.last_valid_action = event.activity_label
        self._clear_recovery()
        self.state = State.COMPLETED if self.expected is None else State.IN_PROGRESS
        self._revision += 1
        message = "Procedure complete." if self.expected is None else f"Step {step.id} complete. Next: {self.expected.description}"
        return self._make(D.VALID, message, event, before=before, skipped=skipped,
                          matching=step.id, speak=True, details={"completed_step_id": step.id})

    def _recover(self, outcome, event, before, match, skipped=()):
        matched = self.definition.steps[match] if match is not None else None
        owner = matched if outcome == D.REPEATED_ACTION else before
        rule = recovery_rule(owner, outcome)
        if rule.action not in (Recovery.IGNORE, Recovery.CONTINUE):
            new_state = State.PAUSED if rule.action == Recovery.PAUSE else State.RECOVERY_REQUIRED
            if self.state != new_state or self._recovery != rule.action:
                self._revision += 1
            self.state, self._recovery = new_state, rule.action
            self._states[self._current_index] = StepState.RETRY_REQUIRED
        message = recovery_message(rule, before, outcome)
        warning = outcome in (D.WRONG_ORDER, D.SKIPPED_STEP) or rule.action in BLOCKING
        return self._make(outcome, message, event, before=before, skipped=skipped,
                          matching=matched.id if matched else None, recovery=rule.action,
                          severity=Severity.WARNING if warning else Severity.INFO,
                          speak=rule.action != Recovery.IGNORE)

    def _make(self, decision, message, event=None, *, before=None, skipped=(), matching=None,
              recovery=None, severity=Severity.INFO, speak=False, display=True, details=None, record=True):
        current = self.expected
        before = before or current
        allowed = self.state in (State.READY, State.IN_PROGRESS, State.RECOVERY_REQUIRED) and self._recovery not in BLOCKING
        suggested = current if allowed else None
        bound_source, bound_session = self._stream or (None, None)
        source = event.metadata.get("source_id") if event else bound_source
        session = event.metadata.get("session_id") if event else bound_session
        stamp = event.timestamp_s if event else self._last_timestamp
        key = f"{self.definition.experiment_id}:{source}:{session}:{self._revision}:{current.id if current else '-'}:{decision.value}:{(recovery or self._recovery or Recovery.CONTINUE).value}"
        now = stamp if stamp is not None else 0.0
        last = self._alerts.get(key)
        should_speak = speak and (last is None or now - last >= self.policy.alert_cooldown_s)
        if should_speak:
            if len(self._alerts) >= self.policy.history_limit:
                self._alerts.pop(next(iter(self._alerts)))
            self._alerts[key] = now
        metadata = {"upstream": deepcopy(event.metadata) if event else {},
                    "bound_source_id": bound_source, "bound_session_id": bound_session, **(details or {})}
        result = GuidanceDecision(decision, self.definition.experiment_id, self.state,
            current.id if current else None, self._current_index if current else None,
            event.activity_label if event else None, before.expected_activity if before else None,
            before.id if before else None, suggested.id if suggested else None,
            suggested.description if suggested else None, recovery or self._recovery,
            message, severity, stamp, event.frame_id if event else None,
            event.event_id if event else None, source, session, event.confidence if event else None,
            tuple(self.completed_steps), tuple(skipped), matching, self._progress(), display, should_speak, key, metadata)
        if record:
            self._history.append(ProcedureHistoryEntry(result.event_id, stamp, decision,
                                 result.expected_step_id, result.current_step_id, message))
        if should_speak or decision in (D.VALID, D.STATE_CHANGED):
            LOGGER.info("procedure=%s decision=%s state=%s step=%s: %s", result.procedure_id,
                        decision.value, self.state.value, result.current_step_id, message)
        return result

    def on_event(self, event: ActivityEvent):
        """Compatibility entry point for historically confirmed events without metadata.

        New integrations use process(), which debounces unconfirmed per-frame inputs.
        """
        if isinstance(event, ActivityEvent) and isinstance(event.metadata, dict):
            event = deepcopy(event)
            if not ({"confirmed", "emitted"} & event.metadata.keys()):
                event.metadata.update(confirmed=True, emitted=True)
            event.metadata.setdefault("source_id", "legacy")
            event.metadata.setdefault("session_id", "legacy")
        result = self.process(event)
        outcome = {D.VALID: StepOutcome.CORRECT, D.WRONG_ORDER: StepOutcome.WRONG_ORDER,
                   D.REPEATED_ACTION: StepOutcome.WRONG_ORDER, D.SKIPPED_STEP: StepOutcome.SKIPPED,
                   D.COMPLETED: StepOutcome.COMPLETED}.get(result.decision, StepOutcome.UNRELATED)
        return outcome, self.current_step()
