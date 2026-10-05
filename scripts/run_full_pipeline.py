"""Run the procedure pipeline demo.

This scaffold intentionally does not instantiate the full perception stack yet,
but it does provide a small, deterministic entry point that validates procedure
configuration and exercises the FSM. The actual perception modules remain an
integration task for later work.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from procedure.fsm import ProcedureFSM, StepOutcome
from procedure.procedure_loader import load_procedure
from shared.schemas.activity_event import ActivityEvent


def _build_demo_event(step: dict, index: int) -> ActivityEvent:
    return ActivityEvent(
        event_id=f"demo_{index}",
        activity_label=step["expected_activity"],
        frame_id=index,
        timestamp_s=float(index),
        start_frame_id=index,
        end_frame_id=index + 1,
        start_timestamp_s=float(index),
        end_timestamp_s=float(index + 1),
        target_object_class=step["target_object"],
        confidence=1.0,
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Load and validate a YAML procedure and exercise the FSM.")
    parser.add_argument("procedure", nargs="?", default="procedures/demo_experiment.yaml", help="Path to a procedure YAML file.")
    parser.add_argument("config_dir", nargs="?", default="configs", help="Path to the folder containing fusion.yaml and classes.yaml.")
    args = parser.parse_args(argv)

    procedure_path = Path(args.procedure)
    config_dir = Path(args.config_dir)

    if not procedure_path.exists():
        print(f"procedure file not found: {procedure_path}", file=sys.stderr)
        return 1
    if not config_dir.exists():
        print(f"config directory not found: {config_dir}", file=sys.stderr)
        return 1

    definition = load_procedure(procedure_path, config_dir)
    fsm = ProcedureFSM(steps=[step.__dict__ for step in definition.steps])

    print(f"Loaded experiment: {definition.experiment_name} ({definition.experiment_id})")
    for index, step in enumerate(definition.steps, start=1):
        event = _build_demo_event(step.__dict__, index)
        outcome, next_step = fsm.on_event(event)
        print(f"step {index}: {step.step_id} -> {outcome.value}")
        if next_step is not None:
            print(f"  next: {next_step.get('id')} ({next_step.get('description')})")

    if not fsm.completed_steps:
        print("No procedure steps completed.")
    else:
        print(f"Completed steps: {fsm.completed_steps}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
