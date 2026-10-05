"""One action/object matcher shared by the FSM and historical stateless helper."""
from shared.schemas.activity_event import ActivityEvent


def matches(event: ActivityEvent, step) -> bool:
    row = step.as_dict() if hasattr(step, "as_dict") else step
    actions = (row.get("expected_activity"), *row.get("alternate_activities", ()))
    target = row.get("target_object")
    return event.activity_label in actions and (target is None or target == event.target_object_class)


def evaluate_step(event: ActivityEvent, expected_steps):
    """Compatibility evaluator; stateful history/recovery belongs to ProcedureFSM."""
    from procedure.fsm import StepOutcome
    if not isinstance(event, ActivityEvent):
        return StepOutcome.UNRELATED
    for index, step in enumerate(expected_steps):
        if matches(event, step):
            return StepOutcome.CORRECT if index == 0 else StepOutcome.SKIPPED
    return StepOutcome.UNRELATED
