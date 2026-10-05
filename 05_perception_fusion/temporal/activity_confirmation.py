"""N-of-M confirmation, target isolation and one emission per continuous action."""
from .evidence_buffer import EvidenceBuffer


class ActivityConfirmation:
    def __init__(self, config):
        self.config = config
        self.buffer = EvidenceBuffer(config["confirmation_window"])
        self.reset()

    def reset(self):
        self.buffer.clear()
        self.key = None
        self.active = None
        self.last_support = None
        self.start = None
        self.event_id = None
        self.counter = getattr(self, "counter", 0)

    def clear_history(self):
        self.buffer.clear()
        self.active = self.last_support = self.start = self.event_id = None

    def update(self, key, fid, ts, label):
        if key != self.key:
            self.clear_history()
            self.key = key
        missing = fid - self.last_support - (label == self.active) if self.last_support is not None else 0
        if self.last_support is not None and missing >= self.config["end_gap_frames"]:
            # End the old occurrence without erasing evidence for a new action.
            self.buffer.discard(self.active)
            self.active = self.last_support = self.start = self.event_id = None
        self.buffer.append(fid, ts, label)
        hits = self.buffer.hits(label)
        if label == "unknown":
            return False, False, None, None
        if label == self.active:
            self.last_support = fid
            return True, False, self.start, self.event_id
        if len(hits) < self.config["confirmation_min_hits"]:
            return False, False, None, None
        self.active = label
        self.start = hits[0]
        self.last_support = fid
        self.counter += 1
        self.event_id = f"activity-{self.counter:06d}"
        self.buffer.clear()
        self.buffer.append(fid, ts, label)
        return True, True, self.start, self.event_id
