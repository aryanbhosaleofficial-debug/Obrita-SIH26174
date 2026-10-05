"""Next-step suggestion helper.

Given the current procedure state, return the next expected step or a completion
message when all expected steps are complete.
"""

from __future__ import annotations

from typing import Any, Sequence


def next_step(current_steps: Sequence[dict[str, Any]], current_index: int) -> dict[str, Any] | None:
    """Return the next pending step from a procedure definition."""

    if current_index >= len(current_steps):
        return None
    return dict(current_steps[current_index])


def completion_message(current_steps: Sequence[dict[str, Any]], current_index: int) -> str:
    """Human-readable completion status."""

    if current_index >= len(current_steps):
        return "Procedure complete."
    step = next_step(current_steps, current_index)
    return f"Next step: {step.get('id')} - {step.get('description')}" if step else "Procedure complete."
