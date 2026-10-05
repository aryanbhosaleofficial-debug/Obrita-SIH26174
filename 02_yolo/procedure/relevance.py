"""Procedure authority excludes incidental taxonomy actions on experiment objects."""

from yolo.procedure.contracts import ProcedureEvent


class ActionRelevance:
    def __init__(self, definition, action_objects):
        self.allowed = frozenset((s.action, s.object_name) for s in definition.steps)
        self.objects = frozenset(s.object_name for s in definition.steps)
        self.taxonomy = dict(action_objects)

    def incidental(self, action, object_name):
        return (
            action not in {"NONE", "UNCERTAIN"}
            and action in self.taxonomy
            and self.taxonomy[action] == object_name
            and object_name in self.objects
            and (action, object_name) not in self.allowed
        )

    def diagnostic(self, action, expected):
        return ProcedureEvent(
            "NON_PROCEDURAL_ACTION",
            expected,
            action.action,
            None,
            action.frame_id,
            action.timestamp_s,
            action.confirmed_monotonic_s,
        )
