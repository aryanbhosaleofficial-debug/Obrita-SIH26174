"""Configurable procedural corrections; no inferred physical reversal."""
from procedure.contracts import DecisionType, RecoveryAction, RecoveryRule
from procedure.procedure_loader import ProcedureStep


def recovery_rule(step: ProcedureStep | None, decision: DecisionType) -> RecoveryRule:
    """Choose an explicit rule or the conservative default for a mismatch."""
    key = {DecisionType.WRONG_ORDER: "wrong_order", DecisionType.SKIPPED_STEP: "skipped",
           DecisionType.REPEATED_ACTION: "repeated", DecisionType.UNEXPECTED_ACTION: "unexpected"}[decision]
    configured = dict(step.recovery).get(key) if step is not None else None
    if configured:
        return configured
    default = RecoveryAction.IGNORE if key in ("repeated", "unexpected") else RecoveryAction.MANUAL_REVIEW
    return RecoveryRule(default)


def recovery_message(rule: RecoveryRule, step: ProcedureStep, decision: DecisionType) -> str:
    """Generate only procedural guidance; physical correction requires configured text."""
    if rule.message:
        return rule.message
    if rule.action == RecoveryAction.RESTART_REQUIRED:
        return "Restart required. Verify the setup before starting a new procedure run."
    if rule.action in (RecoveryAction.PAUSE, RecoveryAction.MANUAL_REVIEW):
        return f"Procedure mismatch. Pause and verify Step {step.id}."
    prefix = {DecisionType.WRONG_ORDER: "Wrong order.", DecisionType.SKIPPED_STEP: "Missing step.",
              DecisionType.REPEATED_ACTION: "Action already completed.",
              DecisionType.UNEXPECTED_ACTION: "Action not in this procedure."}[decision]
    return f"{prefix} Expected {step.id}: {step.description}"
