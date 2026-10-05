"""A bounded window of immutable, image-free evidence snapshots."""

from collections import deque

from shared.schemas.optimization_packet import TemporalFrame


class SequenceBuffer:
    def __init__(self, size: int):
        self._frames: deque[TemporalFrame] = deque(maxlen=size)

    def clear(self) -> None:
        self._frames.clear()

    def append(self, frame: TemporalFrame) -> tuple[TemporalFrame, ...]:
        self._frames.append(frame)
        return tuple(self._frames)
