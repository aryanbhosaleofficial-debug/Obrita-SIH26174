"""Semantic boundary and optional GUI/voice/log sinks. No inference or TTS calls."""
from dataclasses import asdict
import logging
from time import monotonic
from typing import Callable

from procedure.contracts import DecisionType, GuidanceDecision, GuidanceSeverity, ProcedureState, StepState
from procedure.fsm import ProcedureFSM
from shared.schemas.activity_event import ActivityEvent

LOGGER = logging.getLogger(__name__)


def activity_from_dict(payload: dict) -> ActivityEvent:
    """Read the existing ActivityEvent JSONL emitted by scripts/run_fusion.py."""
    from copy import deepcopy
    from shared.enums.module_status import ModuleStatus
    if not isinstance(payload, dict):
        raise ValueError("Activity record must be an object")
    values = deepcopy(payload)
    try:
        values["status"] = ModuleStatus(values.get("status", "ok"))
        return ActivityEvent(**values)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"Invalid ActivityEvent record: {exc}") from exc


def gui_snapshot(decision: GuidanceDecision) -> dict:
    """Dictionary accepted by orbita_gui.adapters.snapshot_from_dict / PipelineBridge."""
    states = {StepState.PENDING: "pending", StepState.ACTIVE: "active",
              StepState.COMPLETED: "done", StepState.SKIPPED: "skipped",
              StepState.RETRY_REQUIRED: "wrong"}
    done = sum(s.state in (StepState.COMPLETED, StepState.SKIPPED) for s in decision.step_states)
    total = len(decision.step_states)
    level = "nominal" if decision.severity == GuidanceSeverity.INFO else "warning"
    if decision.procedure_state in (ProcedureState.PAUSED, ProcedureState.RECOVERY_REQUIRED) and level == "nominal":
        level = "caution"
    stamp = f"{decision.timestamp_s:.3f}" if decision.timestamp_s is not None else ""
    return {
        "status_level": level, "status_text": decision.message,
        "confidence": decision.confidence, "met_seconds": decision.timestamp_s or 0.,
        "stamp": stamp, "spoken": "",  # speech request is not proof of playback
        "steps": [{"id": s.step_id, "text": s.instruction, "state": states[s.state]} for s in decision.step_states],
        "next_step": {"number": decision.next_step_id or "", "head": decision.procedure_state.value.replace("_", " ").title(),
                      "text": decision.message if decision.recovery_action else decision.next_instruction or decision.message,
                      "note": ((decision.recovery_action.value + ": " + (decision.next_instruction or ""))
                               if decision.recovery_action else ""),
                      "confidence": decision.confidence,
                      "progress": done / total if total else 0., "progress_label": f"{done}/{total} steps resolved"},
        "alerts": ([{"t": stamp, "level": level if level != "nominal" else "advisory", "text": decision.message}]
                   if level != "nominal" or decision.procedure_state == ProcedureState.COMPLETED else []),
        "chain": [{"stage": "Procedure", "module": "FSM", "note": f"{decision.observed_action or '-'}: {decision.decision.value}",
                   "status": decision.procedure_state.value}],
        "scene": {"simulated": decision.metadata.get("upstream", {}).get("synthetic") is True}, "local_only": True,
        "procedure_id": decision.procedure_id, "procedure_state": decision.procedure_state.value,
        "current_step_id": decision.current_step_id, "last_activity": decision.observed_action,
        "decision": decision.decision.value, "recovery_action": decision.recovery_action.value if decision.recovery_action else None,
    }


def to_alert(decision: GuidanceDecision, *, clock: Callable[[], float] = monotonic):
    """Reuse AlertEvent; host monotonic dispatch time is distinct from frame time.

    Lifecycle controls have no video frame; the legacy voice contract uses 0
    for that diagnostic field. GuidanceDecision retains None faithfully.
    """
    if not decision.should_speak:
        return None
    from yolo.alerts.contracts import AlertEvent
    if decision.procedure_state == ProcedureState.COMPLETED:
        kind = "COMPLETED"
    elif decision.decision in (DecisionType.WRONG_ORDER, DecisionType.SKIPPED_STEP):
        kind = decision.decision.value.upper()
    elif decision.severity != GuidanceSeverity.INFO:
        kind = "UNEXPECTED_ACTION"
    else:
        kind = "NEXT_STEP"
    return AlertEvent(kind, decision.message, 2 if decision.severity != GuidanceSeverity.INFO else 3,
                      decision.frame_id if decision.frame_id is not None else 0,
                      decision.timestamp_s if decision.timestamp_s is not None else 0.,
                      decision.next_step_id or decision.current_step_id,
                      decision.observed_action or "NONE", clock())


def voice_definition(definition):
    """Adapt configuration for existing AlertManager preloading, without its FSM."""
    from yolo.procedure.contracts import ProcedureDefinition, ProcedureStep
    return ProcedureDefinition(definition.experiment_name, tuple(
        ProcedureStep(index, step.id, step.expected_activity, step.target_object,
                      step.description, f"Expected {step.id}. Verify the procedure.",
                      definition.event_policy.confirmation_frames,
                      round(step.timeout_s * 1000) if step.timeout_s is not None else None)
        for index, step in enumerate(definition.steps, 1)))


class ProcedureIntegration:
    """Deliver GuidanceDecision to optional existing sinks, synchronously.

    gui_sink: PipelineBridge.push_snapshot; alert_sink: AlertManager.enqueue;
    log_sink: EventLog.emit. GUI/audio own their thread queues, never the FSM.
    Supply reset_alerts=AlertManager.reset when sharing its downstream cooldown.
    Sink errors are logged and exposed; they cannot undo or double-apply a step.
    """
    def __init__(self, fsm: ProcedureFSM, *, gui_sink=None, alert_sink=None,
                 log_sink=None, reset_alerts=None, clock=monotonic):
        self.fsm = fsm
        self.gui_sink, self.alert_sink, self.log_sink = gui_sink, alert_sink, log_sink
        self.reset_alerts, self.clock = reset_alerts, clock
        self.last_dispatch_errors: tuple[str, ...] = ()

    def _publish(self, decision):
        calls = []
        if self.gui_sink and decision.should_display:
            calls.append(("gui", self.gui_sink, lambda: gui_snapshot(decision)))
        if self.alert_sink and decision.should_speak:
            calls.append(("alert", self.alert_sink, lambda: to_alert(decision, clock=self.clock)))
        if self.log_sink and (decision.should_speak or decision.decision in (DecisionType.VALID, DecisionType.STATE_CHANGED)):
            calls.append(("log", self.log_sink, lambda: asdict(decision)))
        errors = []
        for name, sink, build_payload in calls:
            try:
                sink(build_payload())
            except Exception as exc:  # external delivery must not replay a state transition
                errors.append(f"{name}: {type(exc).__name__}: {exc}")
                LOGGER.exception("Procedure %s delivery failed", name)
        self.last_dispatch_errors = tuple(errors)
        return decision

    def process(self, event: ActivityEvent | None) -> GuidanceDecision:
        return self._publish(self.fsm.process(event))

    def start(self, **identity) -> GuidanceDecision:
        return self._publish(self.fsm.start(**identity))

    def reset(self) -> GuidanceDecision:
        decision = self.fsm.reset()
        error = None
        if self.reset_alerts:
            try:
                self.reset_alerts()
            except Exception as exc:
                error = f"alert reset: {type(exc).__name__}: {exc}"
                LOGGER.exception("Procedure alert reset failed")
        result = self._publish(decision)
        if error:
            self.last_dispatch_errors += (error,)
        return result

    def pause(self) -> GuidanceDecision:
        return self._publish(self.fsm.pause())

    def resume(self) -> GuidanceDecision:
        return self._publish(self.fsm.resume())

    def abort(self) -> GuidanceDecision:
        return self._publish(self.fsm.abort())
