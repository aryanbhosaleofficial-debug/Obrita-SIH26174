"""Explicit, bounded confirmation and conservative fast/semantic fusion."""

from yolo.alerts.timing import host_time
from yolo.procedure.contracts import ConfirmedAction


class ActionConfirmation:
    def __init__(self, *, consecutive=True, clock=host_time):
        self.consecutive = consecutive
        self.clock = clock
        self.reset()

    def reset(self):
        self.key = None
        self.count = 0
        self.frame_id = -1
        self.latched = None
        self.neutral = 0

    def observe(self, action, object_name, frame_id, timestamp_s, required, source):
        if frame_id <= self.frame_id:
            return None
        gap = self.frame_id >= 0 and frame_id != self.frame_id + 1
        self.frame_id = frame_id
        if action in {"NONE", "UNCERTAIN"}:
            self.key, self.count = None, 0
            self.neutral += 1
            if self.neutral >= required:
                self.latched = None
            return None
        key = (action, object_name)
        self.neutral = 0
        if key == self.latched:
            return None
        self.count = (
            self.count + 1 if key == self.key and not (self.consecutive and gap) else 1
        )
        self.key = key
        if self.count < required:
            return None
        self.latched, self.count = key, 0
        return ConfirmedAction(
            action, object_name, frame_id, timestamp_s, source, self.clock()
        )


class ActionFusion:
    def __init__(self, action_objects, *, clock=host_time, semantic_max_age_s=10):
        self.actions = action_objects
        self.clock = clock
        self.semantic_max_age_s = semantic_max_age_s
        self.fast = ActionConfirmation(clock=clock)
        # Distinct Qwen event results are votes, never copies of the same result
        # on successive display frames. They have their own confirmation count.
        self.semantic = ActionConfirmation(consecutive=False, clock=clock)
        self.reset()

    def reset(self):
        self.fast.reset()
        self.semantic.reset()
        self.last_semantic_event = -1
        self.committed_frame = -1
        self.last_fast = None

    def fast_action(self, candidate, required):
        if (
            candidate.action not in self.actions
            or candidate.object_name != self.actions[candidate.action]
        ):
            return None
        result = self.fast.observe(
            candidate.action,
            candidate.object_name,
            candidate.frame_id,
            candidate.timestamp_s,
            required,
            "fast",
        )
        if result:
            self.last_fast = result
            self.committed_frame = result.frame_id
            self.semantic.reset()
        return result

    def semantic_action(self, result, required, *, current_timestamp_s):
        if result is None or result.event_id <= self.last_semantic_event:
            return None, None
        self.last_semantic_event = result.event_id
        if (
            result.status != "READY"
            or result.action not in self.actions
            or result.object_name != self.actions[result.action]
        ):
            self.semantic.reset()
            return None, None
        disagreement = None
        if (
            self.last_fast
            and result.frame_id <= self.committed_frame
            and result.object_name == self.last_fast.object_name
            and result.action != self.last_fast.action
        ):
            disagreement = {
                "event": "vlm_disagreement",
                "fast": self.last_fast.action,
                "semantic": result.action,
                "frame_id": result.frame_id,
                "event_id": result.event_id,
            }
        if (
            result.frame_id <= self.committed_frame
            or not 0
            <= current_timestamp_s - result.timestamp_s
            <= self.semantic_max_age_s
        ):
            return None, disagreement
        action = self.semantic.observe(
            result.action,
            result.object_name,
            result.frame_id,
            result.timestamp_s,
            required,
            "semantic",
        )
        if action:
            self.committed_frame = action.frame_id
        return action, disagreement
