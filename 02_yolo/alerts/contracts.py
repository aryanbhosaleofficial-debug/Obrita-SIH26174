"""Bounded voice policy and separately owned alert contracts."""

import math
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class VoiceConfig:
    enabled: bool = True
    model_path: Path | None = None
    speak_errors: bool = True
    speak_next_step: bool = True
    speak_success: bool = False
    alert_cooldown_ms: int = 2500
    queue_capacity: int = 8
    cache_entries: int = 512
    cache_bytes: int = 64 * 1024 * 1024
    device: int | None = None
    backend: str = "auto"  # auto | cached_wav | sapi5 | piper
    cache_manifest: Path | None = None
    sapi_voice: str | None = None

    def __post_init__(self):
        if self.backend not in ("auto", "cached_wav", "sapi5", "piper"):
            raise ValueError("voice.backend must be auto, cached_wav, sapi5 or piper")
        if self.sapi_voice is not None and (
            not isinstance(self.sapi_voice, str) or not 1 <= len(self.sapi_voice) <= 128
        ):
            raise ValueError("voice.sapi_voice must be 1..128 characters")
        for name in ("enabled", "speak_errors", "speak_next_step", "speak_success"):
            if type(getattr(self, name)) is not bool:
                raise ValueError(f"voice.{name} must be boolean")
        for name, low, high in (
            ("alert_cooldown_ms", 0, 60000),
            ("queue_capacity", 1, 32),
            ("cache_entries", 1, 512),
            ("cache_bytes", 1024, 128 * 1024 * 1024),
        ):
            value = getattr(self, name)
            if type(value) is not int or not low <= value <= high:
                raise ValueError(f"voice.{name} must be integer {low}..{high}")
        if self.device is not None and (
            type(self.device) is not int or self.device < 0
        ):
            raise ValueError("audio device must be a nonnegative integer")


@dataclass(frozen=True)
class AlertEvent:
    alert_type: str
    message: str
    priority: int
    frame_id: int
    timestamp_s: float
    step_id: str | None
    observed_action: str
    violation_confirmed_timestamp: float

    def __post_init__(self):
        if (
            not isinstance(self.message, str)
            or not self.message.strip()
            or len(self.message) > 600
        ):
            raise ValueError("alert message must contain 1..600 characters")
        if type(self.priority) is not int or not 1 <= self.priority <= 4:
            raise ValueError("alert priority must be 1..4")
        if not math.isfinite(self.violation_confirmed_timestamp):
            raise ValueError("invalid confirmation clock")

    @property
    def key(self):
        return self.alert_type, self.step_id, self.observed_action
