"""Ordered deterministic authority. Later actions never implicitly advance state."""

from yolo.alerts.timing import host_time
from yolo.procedure.contracts import ProcedureEvent, ProcedureState


class ProcedureValidator:
    def __init__(self, definition, *, clock=host_time):
        self.definition = definition
        self.clock = clock
        self.reset()

    def reset(self):
        self.current = 0
        self.completed = []
        self.last_action = "NONE"
        self.status = "ACTIVE"
        self.started_s = self.clock()
        self.timeout_emitted = False

    @property
    def expected(self):
        return (
            self.definition.steps[self.current]
            if self.current < len(self.definition.steps)
            else None
        )

    @property
    def state(self):
        step = self.expected
        return ProcedureState(
            self.current,
            len(self.definition.steps),
            tuple(self.completed),
            self.last_action,
            self.status,
            step.step_id if step else None,
            step.action if step else None,
            step.instruction if step else None,
        )

    def confirmation_frames(self, action):
        for step in (
            self.definition.steps[self.current :]
            + self.definition.steps[: self.current]
        ):
            if step.action == action:
                return step.confirmation_frames
        return self.expected.confirmation_frames if self.expected else 3

    def observe(self, action):
        step = self.expected
        if action.action in {"NONE", "UNCERTAIN"}:
            return None
        self.last_action = action.action
        expected = step.action if step else None
        skipped = ()
        if (
            step
            and action.action == step.action
            and action.object_name == step.object_name
        ):
            self.completed.append(step.step_id)
            self.current += 1
            self.started_s = self.clock()
            self.timeout_emitted = False
            self.status = "COMPLETED" if self.expected is None else "ACTIVE"
            event = "STEP_COMPLETED"
        elif action.action in [s.action for s in self.definition.steps[: self.current]]:
            event = "REPEATED_ACTION"
        else:
            later = next(
                (
                    s
                    for s in self.definition.steps[self.current + 1 :]
                    if s.action == action.action and s.object_name == action.object_name
                ),
                None,
            )
            if later:
                event = (
                    "SKIPPED_STEP"
                    if step and later.object_name == step.object_name
                    else "WRONG_ORDER"
                )
                skipped = tuple(
                    s.step_id
                    for s in self.definition.steps[self.current : later.index - 1]
                )
            else:
                event = "UNEXPECTED_ACTION"
            if step:
                self.status = event
        return ProcedureEvent(
            event,
            expected,
            action.action,
            step.step_id if step else None,
            action.frame_id,
            action.timestamp_s,
            action.confirmed_monotonic_s,
            skipped,
        )

    def tick(self, frame_id, timestamp_s):
        step = self.expected
        now = self.clock()
        if (
            step
            and step.timeout_ms is not None
            and not self.timeout_emitted
            and (now - self.started_s) * 1000 >= step.timeout_ms
        ):
            self.timeout_emitted = True
            self.status = "STEP_TIMEOUT"
            return ProcedureEvent(
                "STEP_TIMEOUT",
                step.action,
                "NONE",
                step.step_id,
                frame_id,
                timestamp_s,
                now,
            )
        return None
