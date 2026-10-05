"""Step validation logic for Procedure FSM.

Input:
    ActivityEvent + current procedure state

Output:
    StepOutcome (correct / wrong order / skipped / unrelated)

Owner:
    Procedure FSM (downstream consumer of Module 05)
"""

from __future__ import annotations

from typing import Iterable

from shared.schemas.activity_event import ActivityEvent
from procedure.fsm import StepOutcome


def evaluate_step(event: ActivityEvent, expected_steps: Iterable[dict]) -> StepOutcome:
    """Evaluate a single event against the expectation list.

    The logic is intentionally lightweight and deterministic: an event is
    considered correct only when it matches the current expected step. A match to
    a later step is a skipped-step signal; a match to a non-expected earlier step
    is wrong-order; an unrelated event is simply not associated with the
    procedure.
    """

    if event.activity_label is None:
        return StepOutcome.UNRELATED

    for index, step in enumerate(expected_steps):
        if step.get("expected_activity") == event.activity_label:
            if step.get("target_object") and event.target_object_class is not None:
                if step.get("target_object") != event.target_object_class:
                    continue
            if index == 0:
                return StepOutcome.CORRECT
            return StepOutcome.SKIPPED

    return StepOutcome.UNRELATED
