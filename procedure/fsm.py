"""Procedure finite-state machine.

The project is still scaffolded, but the procedure logic is the core runtime path
that the rest of the pipeline is intended to feed. This minimal state machine is
kept intentionally small: it tracks the current expected step, accepts
ActivityEvent objects, and reports whether the event matches the expected task,
comes too early, skips ahead, or is unrelated.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Sequence

from shared.schemas.activity_event import ActivityEvent


class StepOutcome(str, Enum):
    """Result of validating one ActivityEvent against the procedure."""

    CORRECT = "correct"
    WRONG_ORDER = "wrong_order"
    SKIPPED = "skipped"
    UNRELATED = "unrelated"
    COMPLETED = "completed"


@dataclass
class ProcedureFSM:
    """Tracks progress through an ordered procedure definition."""

    steps: Sequence[dict[str, Any]] = field(default_factory=list)
    current_index: int = 0
    completed_steps: list[str] = field(default_factory=list)
    history: list[dict[str, Any]] = field(default_factory=list)

    def reset(self) -> None:
        self.current_index = 0
        self.completed_steps = []
        self.history = []

    def current_step(self) -> dict[str, Any] | None:
        if self.current_index >= len(self.steps):
            return None
        return dict(self.steps[self.current_index])

    def _advance(self) -> None:
        current = self.current_step()
        if current is None:
            return
        self.completed_steps.append(str(current.get("id", self.current_index)))
        self.current_index += 1

    def on_event(self, event: ActivityEvent) -> tuple[StepOutcome, dict[str, Any] | None]:
        """Process one ActivityEvent and report the procedure outcome."""

        if not self.steps:
            return StepOutcome.UNRELATED, None

        if self.current_index >= len(self.steps):
            return StepOutcome.COMPLETED, None

        current = self.current_step()
        if current is None:
            return StepOutcome.COMPLETED, None

        expected_activity = current.get("expected_activity")
        expected_object = current.get("target_object")

        if expected_activity == event.activity_label:
            if expected_object is None or expected_object == event.target_object_class:
                self._advance()
                outcome = StepOutcome.CORRECT
                self.history.append(
                    {
                        "event_id": event.event_id,
                        "step_id": current.get("id"),
                        "outcome": outcome.value,
                    }
                )
                return outcome, self.current_step()

        for index, step in enumerate(self.steps):
            if step.get("expected_activity") == event.activity_label:
                if index < self.current_index:
                    outcome = StepOutcome.WRONG_ORDER
                else:
                    outcome = StepOutcome.SKIPPED
                self.history.append(
                    {
                        "event_id": event.event_id,
                        "step_id": step.get("id"),
                        "outcome": outcome.value,
                    }
                )
                return outcome, self.current_step()

        self.history.append(
            {
                "event_id": event.event_id,
                "step_id": None,
                "outcome": StepOutcome.UNRELATED.value,
            }
        )
        return StepOutcome.UNRELATED, self.current_step()


__all__ = ["ProcedureFSM", "StepOutcome"]
