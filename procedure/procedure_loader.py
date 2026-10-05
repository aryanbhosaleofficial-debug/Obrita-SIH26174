"""Strict offline YAML loader; the existing experiment/steps format is retained."""
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any
import math

import yaml

from procedure.contracts import EventPolicy, RecoveryAction, RecoveryRule


@dataclass(frozen=True)
class ProcedureStep:
    step_id: str
    description: str
    expected_activity: str
    target_object: str | None
    optional: bool = False
    alternate_activities: tuple[str, ...] = ()
    timeout_s: float | None = None  # Metadata only; no implicit wall-clock timeout.
    recovery: tuple[tuple[str, RecoveryRule], ...] = ()

    @property
    def id(self) -> str:
        return self.step_id

    def as_dict(self) -> dict[str, Any]:
        return {"id": self.step_id, "step_id": self.step_id,
                "description": self.description, "expected_activity": self.expected_activity,
                "target_object": self.target_object, "optional": self.optional,
                "alternate_activities": list(self.alternate_activities),
                "timeout_s": self.timeout_s,
                "recovery": {k: {"action": r.action.value, "message": r.message}
                             for k, r in self.recovery}}


@dataclass(frozen=True)
class ProcedureDefinition:
    experiment_id: str
    experiment_name: str
    version: str
    steps: tuple[ProcedureStep, ...]
    event_policy: EventPolicy = field(default_factory=EventPolicy)


def _text(value, name, limit=128):
    if not isinstance(value, str) or not value.strip() or value != value.strip() or len(value) > limit:
        raise ValueError(f"{name} must be nonempty text of at most {limit} characters")
    return value


def _keys(value, allowed, name):
    if not isinstance(value, dict):
        raise ValueError(f"{name} must be a mapping")
    extra = set(value) - set(allowed)
    if extra:
        raise ValueError(f"Unknown {name} fields: {sorted(extra, key=str)}")


def _strings(value, name):
    if not isinstance(value, (list, tuple)):
        raise ValueError(f"{name} must be a list")
    result = tuple(_text(v, name) for v in value)
    if len(set(result)) != len(result):
        raise ValueError(f"Duplicate values in {name}")
    return result


def _number(value, name, low, high):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or not low <= value <= high:
        raise ValueError(f"{name} must be finite in [{low}, {high}]")
    return value


def _policy(payload):
    _keys(payload, EventPolicy.__dataclass_fields__, "event_policy")
    values = asdict(EventPolicy()) | payload
    for name in ("allow_missing_confidence", "require_identity"):
        if type(values[name]) is not bool:
            raise ValueError(f"{name} must be boolean")
    for name, low, high in (("confirmation_frames", 2, 100), ("history_limit", 1, 10000), ("dedup_limit", 1, 100000)):
        if type(values[name]) is not int or not low <= values[name] <= high:
            raise ValueError(f"{name} must be an integer in [{low}, {high}]")
    _number(values["min_confidence"], "min_confidence", 0, 1)
    _number(values["max_gap_s"], "max_gap_s", 0.001, 3600)
    _number(values["alert_cooldown_s"], "alert_cooldown_s", 0, 3600)
    values["ignored_actions"] = _strings(values["ignored_actions"], "ignored_actions")
    return EventPolicy(**values)


def _steps(payload, allowed_activities=None, allowed_objects=None):
    if not isinstance(payload, (list, tuple)) or not payload:
        raise ValueError("Procedure must define nonempty steps")
    result, seen = [], set()
    for order, row in enumerate(payload, 1):
        _keys(row, {"id", "step_id", "order", "description", "expected_activity", "target_object",
                    "optional", "alternate_activities", "timeout_s", "recovery"}, "step")
        sid = _text(row.get("id"), "step.id")
        if sid in seen:
            raise ValueError(f"Duplicate step id '{sid}'")
        if "step_id" in row and row["step_id"] != sid:
            raise ValueError("step_id and id disagree")
        if "order" in row and (type(row["order"]) is not int or row["order"] != order):
            raise ValueError("step.order must match contiguous list order starting at 1")
        description = _text(row.get("description"), f"{sid}.description", 240)
        activity = _text(row.get("expected_activity"), f"{sid}.expected_activity")
        if "target_object" not in row:
            raise ValueError(f"{sid}.target_object is required (null explicitly matches any object)")
        obj = row["target_object"]
        if obj is not None:
            _text(obj, f"{sid}.target_object")
        optional = row.get("optional", False)
        if type(optional) is not bool:
            raise ValueError(f"{sid}.optional must be boolean")
        alternatives = _strings(row.get("alternate_activities", []), "alternate_activities")
        if activity in alternatives:
            raise ValueError("Primary activity cannot also be an alternate")
        actions = {activity, *alternatives}
        if allowed_activities is not None and not actions <= allowed_activities:
            raise ValueError(f"{sid}: activities are not in the configured vocabulary")
        if obj is not None and allowed_objects is not None and obj not in allowed_objects:
            raise ValueError(f"{sid}: target_object is not in the configured vocabulary")
        for prior in result:
            overlap = actions & {prior.expected_activity, *prior.alternate_activities}
            if overlap and (obj is None or prior.target_object is None or obj == prior.target_object):
                raise ValueError(f"Ambiguous duplicate action/object match: {prior.id} and {sid}")
        timeout = row.get("timeout_s")
        if timeout is not None:
            _number(timeout, "timeout_s", 0.001, 86400)
        policies = row.get("recovery", {})
        _keys(policies, {"wrong_order", "skipped", "repeated", "unexpected"}, "recovery")
        recovery = []
        for key, rule in policies.items():
            _keys(rule, {"action", "message"}, f"recovery.{key}")
            try:
                action = RecoveryAction(rule.get("action"))
            except (ValueError, TypeError) as exc:
                raise ValueError(f"Unknown recovery action in {sid}.{key}") from exc
            message = rule.get("message")
            if message is not None:
                _text(message, "recovery.message", 300)
            recovery.append((key, RecoveryRule(action, message)))
        seen.add(sid)
        result.append(ProcedureStep(sid, description, activity, obj, optional, alternatives, timeout, tuple(recovery)))
    return tuple(result)


def validate_definition(definition: ProcedureDefinition) -> ProcedureDefinition:
    """Validate programmatically supplied definitions at the same boundary as YAML."""
    if not isinstance(definition, ProcedureDefinition):
        raise TypeError("Expected ProcedureDefinition")
    for name in ("experiment_id", "experiment_name", "version"):
        _text(getattr(definition, name), name)
    steps = _steps([s.as_dict() for s in definition.steps])
    policy = _policy(asdict(definition.event_policy))
    if any(set((s.expected_activity, *s.alternate_activities)) & set(policy.ignored_actions) for s in steps):
        raise ValueError("Expected activities cannot also be ignored_actions")
    return ProcedureDefinition(definition.experiment_id, definition.experiment_name, definition.version, steps, policy)


def definition_from_steps(steps) -> ProcedureDefinition:
    """Compatibility input for historical ProcedureFSM(steps=[...]) callers."""
    rows = [dict(s) for s in steps]
    for row in rows:
        row.setdefault("description", str(row.get("id", "Procedure step")))
        row.setdefault("target_object", None)
    return validate_definition(ProcedureDefinition("legacy_procedure", "Legacy procedure", "1", _steps(rows)))


def _load_yaml(path):
    try:
        payload = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        raise ValueError(f"Invalid procedure YAML: {path}: {exc}") from exc
    if not isinstance(payload, dict):
        raise ValueError(f"'{path}' must contain a YAML mapping")
    return payload


def load_procedure(procedure_path: str | Path, config_dir: str | Path | None = None) -> ProcedureDefinition:
    """Load experiment/steps YAML; inline vocabulary or existing configs validate labels."""
    path = Path(procedure_path)
    payload = _load_yaml(path)
    _keys(payload, {"experiment", "steps", "vocabulary", "event_policy"}, "procedure")
    experiment = payload.get("experiment", {})
    _keys(experiment, {"id", "name", "version"}, "experiment")
    for key in ("id", "name", "version"):
        _text(experiment.get(key), f"experiment.{key}")
    if "vocabulary" in payload:
        vocabulary = payload["vocabulary"]
        _keys(vocabulary, {"activities", "objects"}, "vocabulary")
        activities = set(_strings(vocabulary.get("activities"), "vocabulary.activities"))
        objects = set(_strings(vocabulary.get("objects"), "vocabulary.objects"))
    else:
        directory = Path(config_dir) if config_dir is not None else path.resolve().parent.parent / "configs"
        activities = set(_strings(_load_yaml(directory / "fusion.yaml").get("activities", {}).get("labels"), "activities.labels"))
        classes = _load_yaml(directory / "classes.yaml").get("classes")
        if not isinstance(classes, list) or not all(isinstance(c, dict) and isinstance(c.get("name"), str) for c in classes):
            raise ValueError("classes.yaml must define named classes")
        objects = {c["name"] for c in classes}
    definition = ProcedureDefinition(experiment["id"], experiment["name"], experiment["version"],
                                     _steps(payload.get("steps"), activities, objects),
                                     _policy(payload.get("event_policy", {})))
    return validate_definition(definition)
