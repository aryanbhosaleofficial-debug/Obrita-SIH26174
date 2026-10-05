"""Strict line-oriented Markdown, never interpreted by an LLM."""

import re
from pathlib import Path

from yolo.procedure.contracts import ProcedureDefinition, ProcedureStep
from yolo.semantic.contracts import default_actions


class ProcedureError(ValueError):
    pass


def _integer(values, index, key, upper):
    value = values[key]
    if not re.fullmatch(r"[1-9][0-9]*", value) or int(value) > upper:
        raise ProcedureError(f"step {index}: {key} must be integer 1..{upper}")
    return int(value)


def parse_procedure(text, action_objects=None):
    actions = default_actions() if action_objects is None else action_objects
    if not isinstance(text, str) or len(text) > 65536:
        raise ProcedureError("procedure must be UTF-8 Markdown at most 64 KiB")
    sections: list[tuple[int, dict[str, str]]] = []
    name = None
    fields: dict[str, str] | None = None
    required = {
        "id",
        "action",
        "object",
        "instruction",
        "warning",
        "confirmation_frames",
    }
    for number, raw in enumerate(text.splitlines(), 1):
        line = raw.strip()
        if not line:
            continue
        if name is None:
            if not line.startswith("# Experiment: ") or not line[14:].strip():
                raise ProcedureError(f"line {number}: expected # Experiment: NAME")
            name = line[14:].strip()
            if len(name) > 160:
                raise ProcedureError("experiment name exceeds 160 characters")
            continue
        match = re.fullmatch(r"## Step ([1-9][0-9]*)", line)
        if match:
            index = int(match[1])
            if index != len(sections) + 1 or index > 64:
                raise ProcedureError(f"line {number}: steps must be consecutive 1..64")
            fields = {}
            sections.append((index, fields))
            continue
        match = re.fullmatch(r"- ([a-z_]+):\s*(.*)", line)
        if match is None or fields is None:
            raise ProcedureError(f"line {number}: malformed step section or field")
        key, value = match.groups()
        if key not in required | {"timeout_ms"} or key in fields or not value:
            raise ProcedureError(
                f"line {number}: unknown, duplicate or empty field {key}"
            )
        fields[key] = value
    if name is None or not sections:
        raise ProcedureError("procedure requires an experiment and at least one step")
    steps = []
    ids = set()
    for index, values in sections:
        missing = required - values.keys()
        if missing:
            raise ProcedureError(f"step {index}: missing fields {sorted(missing)}")
        step_id = values["id"]
        if not re.fullmatch(r"[a-z][a-z0-9_]{0,63}", step_id) or step_id in ids:
            raise ProcedureError(f"step {index}: invalid or duplicate id {step_id}")
        ids.add(step_id)
        action = values["action"]
        obj = None if values["object"] == "null" else values["object"]
        if (
            action not in actions
            or action in {"NONE", "UNCERTAIN"}
            or obj != actions[action]
        ):
            raise ProcedureError(f"step {index}: unknown action or inconsistent object")
        for key in ("instruction", "warning"):
            if len(values[key]) > 240:
                raise ProcedureError(f"step {index}: {key} exceeds 240 characters")

        confirmation = _integer(values, index, "confirmation_frames", 120)
        timeout = (
            _integer(values, index, "timeout_ms", 86400000)
            if "timeout_ms" in values
            else None
        )
        steps.append(
            ProcedureStep(
                index,
                step_id,
                action,
                obj,
                values["instruction"],
                values["warning"],
                confirmation,
                timeout,
            )
        )
    return ProcedureDefinition(name, tuple(steps))


def load_procedure(path, action_objects=None):
    path = Path(path)
    if path.stat().st_size > 65536:
        raise ProcedureError("procedure exceeds 64 KiB")
    return parse_procedure(path.read_text(encoding="utf-8-sig"), action_objects)
