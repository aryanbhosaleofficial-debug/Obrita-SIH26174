"""
Procedure finite-state machine.

Implementation status:
    Scaffold only.

Input:
    ActivityEvent (shared/schemas/activity_event.py) from Module 05 — Perception Fusion
    Procedure definition loaded by procedure_loader.py from procedures/*.yaml

Output:
    StepOutcome per event, current step, next-step suggestion (via next_step.py)

Owner:
    Procedure FSM (downstream consumer of Module 05)

Scope:
    This is the ONLY place where procedure order is judged (correct step,
    wrong-order step, skipped step). Perception modules 01-05 only report
    what was observed.
"""

from enum import Enum


class StepOutcome(str, Enum):
    """Result of validating one ActivityEvent against the procedure."""

    CORRECT = "correct"            # event matches the current expected step
    WRONG_ORDER = "wrong_order"    # event matches a step that is not allowed yet
    SKIPPED = "skipped"            # event matches a later step; earlier steps were skipped
    UNRELATED = "unrelated"        # event does not match any procedure step
    COMPLETED = "completed"        # procedure already finished


# TODO: ProcedureFSM holding the ordered steps and the index of the current step.
# TODO: on_event(event: ActivityEvent) -> StepOutcome, using step_validator.py.
# TODO: Keep a history of (event_id, step_id, outcome) for outputs/events/.
# TODO: Reset / restart support for demo runs.
