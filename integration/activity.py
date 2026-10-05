"""One explicit semantic mapping boundary; never classify pixels or invent confidence."""
from copy import deepcopy
from dataclasses import replace
from pathlib import Path

import yaml

from procedure.events import validate_event
from shared.schemas.activity_event import ActivityEvent


class ActivityAdapter:
    """Pass through Module 05 events, or apply a reviewed label/object mapping."""

    def __init__(self, rules=(), *, semantics="native"):
        self.rules = tuple(rules)
        self.semantics = semantics

    @classmethod
    def from_yaml(cls, path):
        data = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
        if not isinstance(data, dict) or set(data) != {"semantics", "mappings"}:
            raise ValueError("event map requires semantics and mappings")
        if data["semantics"] not in ("reviewed", "demo_proxy"):
            raise ValueError("event map semantics must be reviewed or demo_proxy")
        if not isinstance(data["mappings"], list) or not data["mappings"]:
            raise ValueError("event map mappings must be a nonempty list")
        rules, seen = [], set()
        for row in data["mappings"]:
            if not isinstance(row, dict) or set(row) != {"activity", "object", "maps_to"}:
                raise ValueError("each event mapping requires activity, object, maps_to")
            if any(not isinstance(v, str) or not v.strip() for v in row.values()):
                raise ValueError("event mapping values must be nonempty strings")
            key = (row["activity"], row["object"])
            if key in seen:
                raise ValueError("ambiguous duplicate event mapping")
            seen.add(key)
            rules.append((row["activity"], row["object"], row["maps_to"]))
        return cls(rules, semantics=data["semantics"])

    def validate_vocabulary(self, definition, fusion_config):
        labels = set(fusion_config["activities"]["labels"])
        for activity, obj, mapped in self.rules:
            if activity not in labels:
                raise ValueError(f"event map input is not a Module 05 label: {activity}")
            if not any(mapped in (s.expected_activity, *s.alternate_activities)
                       and (s.target_object is None or s.target_object == obj) for s in definition.steps):
                raise ValueError(f"event map output/object is not in procedure: {mapped}/{obj}")
        for step in definition.steps:
            actions = {step.expected_activity, *step.alternate_activities}
            mapped = any(out in actions and (step.target_object is None or obj == step.target_object)
                         for _, obj, out in self.rules)
            if not actions & labels and not mapped:
                raise ValueError(f"HAR cannot produce {step.expected_activity}; choose a matching procedure or an explicit --event-map")

    def adapt(self, event: ActivityEvent) -> ActivityEvent:
        """Preserve identity, target, confidence and upstream confirmation exactly."""
        validate_event(event, require_identity=True)
        metadata = deepcopy(event.metadata)
        label = next((out for action, obj, out in self.rules
                      if action == event.activity_label and obj == event.target_object_class), event.activity_label)
        if label != event.activity_label:
            metadata.update(original_activity=event.activity_label, mapping_semantics=self.semantics)
        return replace(event, activity_label=label, metadata=metadata)
