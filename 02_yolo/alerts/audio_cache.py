"""Procedure-scoped PCM cache: no persistent temporary audio files."""

from collections import OrderedDict
from dataclasses import dataclass


@dataclass(frozen=True)
class AudioClip:
    pcm: bytes
    sample_rate: int
    channels: int = 1
    source: str | None = None  # backend that produced the PCM (logging only)

    def __post_init__(self):
        if (
            not isinstance(self.pcm, bytes)
            or not self.pcm
            or self.channels not in (1, 2)
            or not 8000 <= self.sample_rate <= 96000
            or len(self.pcm) % (2 * self.channels)
            or len(self.pcm) > self.sample_rate * self.channels * 2 * 20
        ):
            raise ValueError(
                "audio clip must be nonempty PCM16, mono/stereo, <=20 seconds"
            )


class AudioCache:
    def __init__(self, max_entries=512, max_bytes=64 * 1024 * 1024):
        self.max_entries, self.max_bytes = max_entries, max_bytes
        self.items = OrderedDict()
        self.bytes_used = 0

    def get(self, message):
        return self.items.get(message)

    def put(self, message, clip, *, evict=False):
        if message in self.items:
            return
        if len(clip.pcm) > self.max_bytes:
            raise ValueError("single voice clip exceeds cache limit")
        while (
            len(self.items) >= self.max_entries
            or self.bytes_used + len(clip.pcm) > self.max_bytes
        ):
            if not evict:
                raise ValueError("procedure alert cache exceeds configured bounds")
            _, removed = self.items.popitem(last=False)
            self.bytes_used -= len(removed.pcm)
        self.items[message] = clip
        self.bytes_used += len(clip.pcm)

    def clear(self):
        self.items.clear()
        self.bytes_used = 0
