"""Bounded frame-keyed support history; gaps do not become invented hits."""
from collections import deque


class EvidenceBuffer:
    def __init__(self, window):
        self.window = window
        self.items = deque(maxlen=window)

    def clear(self):
        self.items.clear()

    def append(self, frame_id, timestamp, label):
        while self.items and self.items[0][0] <= frame_id - self.window:
            self.items.popleft()
        self.items.append((frame_id, timestamp, label))

    def hits(self, label):
        return [(fid, ts) for fid, ts, value in self.items if value == label]

    def discard(self, label):
        self.items = deque((row for row in self.items if row[2] != label), maxlen=self.window)
