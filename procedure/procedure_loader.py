"""Procedure definition loader.

Input:
    procedures/*.yaml

Output:
    Ordered list of validated procedure steps.

Owner:
    Procedure FSM (downstream consumer of Module 05)
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml


@dataclass(frozen=True)
class ProcedureStep:
    """One step in an experiment procedure."""

    step_id: str
    description: str
    expected_activity: str
    target_object: str
    optional: bool = False

    @property
    def id(self) -> str:
        return self.step_id

    def as_dict(self) -> dict[str, Any]:
        return {
            "id": self.step_id,
            "step_id": self.step_id,
            "description": self.description,
            "expected_activity": self.expected_activity,
            "target_object": self.target_object,
            "optional": self.optional,
        }


@dataclass(frozen=True)
class ProcedureDefinition:
    """Validated procedure definition."""

    experiment_id: str
    experiment_name: str
    version: str
    steps: list[ProcedureStep]


def _load_yaml(path: str | Path) -> dict[str, Any]:
    config_path = Path(path)
    with config_path.open("r", encoding="utf-8") as handle:
        payload = yaml.safe_load(handle) or {}
    if not isinstance(payload, dict):
        raise ValueError(f"Procedure file '{config_path}' did not contain a mapping at the root.")
    return payload


def _activity_labels(config_dir: str | Path) -> set[str]:
    config_path = Path(config_dir) / "fusion.yaml"
    payload = _load_yaml(config_path)
    labels = payload.get("activities", {}).get("labels", [])
    if not isinstance(labels, list):
        raise ValueError(f"'{config_path}' is missing a valid 'activities.labels' list.")
    return {str(label) for label in labels}


def _object_classes(config_dir: str | Path) -> set[str]:
    config_path = Path(config_dir) / "classes.yaml"
    payload = _load_yaml(config_path)
    classes = payload.get("classes", [])
    if not isinstance(classes, list):
        raise ValueError(f"'{config_path}' is missing a valid 'classes' list.")
    names = set()
    for item in classes:
        if isinstance(item, dict):
            name = item.get("name")
            if name is not None:
                names.add(str(name))
    return names


def load_procedure(procedure_path: str | Path, config_dir: str | Path | None = None) -> ProcedureDefinition:
    """Load and validate a YAML procedure definition.

    The file format follows the contract documented in `procedures/README.md` and
    `configs/*.yaml`. Invalid or incomplete definitions raise ValueError.
    """

    procedure_file = Path(procedure_path)
    if config_dir is None:
        config_dir = procedure_file.parents[1] / "configs"

    payload = _load_yaml(procedure_file)
    experiment = payload.get("experiment", {})
    if not isinstance(experiment, dict):
        raise ValueError(f"'{procedure_file}' is missing a valid 'experiment' section.")

    experiment_id = experiment.get("id")
    experiment_name = experiment.get("name")
    version = experiment.get("version")
    if not isinstance(experiment_id, str) or not experiment_id:
        raise ValueError(f"'{procedure_file}' has an invalid experiment.id value.")
    if not isinstance(experiment_name, str) or not experiment_name:
        raise ValueError(f"'{procedure_file}' has an invalid experiment.name value.")
    if not isinstance(version, str) or not version:
        raise ValueError(f"'{procedure_file}' has an invalid experiment.version value.")

    steps_payload = payload.get("steps", [])
    if not isinstance(steps_payload, list):
        raise ValueError(f"'{procedure_file}' has an invalid 'steps' list.")
    if not steps_payload:
        raise ValueError(f"'{procedure_file}' does not define any procedure steps.")

    allowed_activities = _activity_labels(config_dir)
    allowed_objects = _object_classes(config_dir)
    seen_step_ids: set[str] = set()
    validated_steps: list[ProcedureStep] = []

    for index, step in enumerate(steps_payload, start=1):
        if not isinstance(step, dict):
            raise ValueError(f"Step #{index} in '{procedure_file}' is not a mapping.")

        step_id = step.get("id")
        description = step.get("description")
        expected_activity = step.get("expected_activity")
        target_object = step.get("target_object")
        optional = bool(step.get("optional", False))

        if not isinstance(step_id, str) or not step_id:
            raise ValueError(f"Step #{index} in '{procedure_file}' is missing a valid id.")
        if step_id in seen_step_ids:
            raise ValueError(f"Duplicate step id '{step_id}' in '{procedure_file}'.")
        if not isinstance(description, str) or not description:
            raise ValueError(f"Step '{step_id}' is missing a valid description.")
        if not isinstance(expected_activity, str) or not expected_activity:
            raise ValueError(f"Step '{step_id}' is missing a valid expected_activity.")
        if expected_activity not in allowed_activities:
            raise ValueError(
                f"Step '{step_id}' expected_activity '{expected_activity}' is not in '{Path(config_dir) / 'fusion.yaml'}'."
            )
        if not isinstance(target_object, str) or not target_object:
            raise ValueError(f"Step '{step_id}' is missing a valid target_object.")
        if target_object not in allowed_objects:
            raise ValueError(
                f"Step '{step_id}' target_object '{target_object}' is not in '{Path(config_dir) / 'classes.yaml'}'."
            )

        seen_step_ids.add(step_id)
        validated_steps.append(
            ProcedureStep(
                step_id=step_id,
                description=description,
                expected_activity=expected_activity,
                target_object=target_object,
                optional=optional,
            )
        )

    return ProcedureDefinition(
        experiment_id=str(experiment_id),
        experiment_name=str(experiment_name),
        version=str(version),
        steps=validated_steps,
    )


__all__ = ["ProcedureDefinition", "ProcedureStep", "load_procedure"]
