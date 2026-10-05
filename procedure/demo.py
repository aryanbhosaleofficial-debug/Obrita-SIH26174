"""Offline semantic-event demo and replay. Synthetic actions are explicitly labelled."""
import argparse
from dataclasses import asdict
import json
import logging
from pathlib import Path
import sys

from procedure import ProcedureFSM, ProcedureIntegration, load_procedure
from procedure.contracts import DecisionType
from procedure.integration import activity_from_dict
from shared.schemas.activity_event import ActivityEvent

ROOT = Path(__file__).resolve().parents[1]
SCENARIOS = ("correct", "wrong-order", "skip", "repeated", "recovery")


def synthetic_events(definition, scenario="correct"):
    """Scenario indices select configured steps; no experiment logic lives in FSM."""
    if scenario != "correct" and len(definition.steps) != 4:
        raise ValueError("Error/recovery demo scenarios require the four-step demo procedure")
    sequences = {"correct": range(len(definition.steps)), "wrong-order": (2,),
                 "skip": (0, 2), "repeated": (0, 0), "recovery": (0, 2, 1, 2, 3)}
    for frame, index in enumerate(sequences[scenario], 1):
        step = definition.steps[index]
        yield ActivityEvent(f"demo-{scenario}-{frame}", step.expected_activity,
                            frame, float(frame), frame, frame, float(frame), float(frame),
                            target_object_class=step.target_object, confidence=0.95,
                            metadata={"source_id": "synthetic-har", "session_id": scenario,
                                      "procedure_id": definition.experiment_id,
                                      "confirmed": True, "emitted": True, "synthetic": True})


def replay_events(path):
    with Path(path).open(encoding="utf-8") as stream:
        for line_number, line in enumerate(stream, 1):
            if line.strip():
                try:
                    yield activity_from_dict(json.loads(line))
                except (ValueError, TypeError) as exc:
                    raise ValueError(f"Event line {line_number}: {exc}") from exc


def run_demo(definition, *, scenario="correct", events=None, json_output=False, legacy_output=False):
    """Shared orchestration for the new CLI and the historical main.py launcher."""
    integration = ProcedureIntegration(ProcedureFSM(definition=definition))
    result = integration.start()
    if not json_output:
        print(f"Loaded experiment: {definition.experiment_name} ({definition.experiment_id})")
        print("Mode: replayed ActivityEvent records" if events is not None else f"Mode: synthetic recognized activities ({scenario})")
        print(result.message)
    for index, event in enumerate(events if events is not None else synthetic_events(definition, scenario), 1):
        result = integration.process(event)
        if json_output:
            print(json.dumps(asdict(result), allow_nan=False))
        elif legacy_output:
            outcome = "correct" if result.decision == DecisionType.VALID else result.decision.value
            step_id = result.metadata.get("completed_step_id", result.expected_step_id)
            print(f"step {index}: {step_id} -> {outcome}")
            if result.next_step_id:
                print(f"  next: {result.next_step_id} ({result.next_instruction})")
        else:
            print(f"[{event.timestamp_s:.1f}] {event.activity_label} -> {result.decision.value.upper()}")
            print(f"  {result.message}")
            if result.skipped_steps:
                print(f"  Missing: {', '.join(result.skipped_steps)}")
    if not json_output:
        print(f"Completed steps: {list(result.completed_steps)}")
        print(f"State: {result.procedure_state.value}")
    return 0


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--procedure", default="red_yellow_box", help="procedure name or YAML path")
    parser.add_argument("--config-dir", type=Path, default=None)
    source = parser.add_mutually_exclusive_group()
    source.add_argument("--scenario", choices=(*SCENARIOS, "all"), default="correct")
    source.add_argument("--events", type=Path, help="existing ActivityEvent JSONL, no camera/model loading")
    parser.add_argument("--json", action="store_true", help="emit GuidanceDecision JSONL")
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args(argv)
    if args.verbose:
        logging.basicConfig(level=logging.INFO)
    path = Path(args.procedure)
    if not path.suffix and not path.exists():
        path = ROOT / "procedures" / f"{args.procedure}.yaml"
    try:
        definition = load_procedure(path, args.config_dir)
        scenarios = SCENARIOS if args.scenario == "all" else (args.scenario,)
        for scenario in scenarios:
            run_demo(definition, scenario=scenario,
                     events=replay_events(args.events) if args.events else None, json_output=args.json)
        return 0
    except (OSError, ValueError) as exc:
        print(f"Procedure demo: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
