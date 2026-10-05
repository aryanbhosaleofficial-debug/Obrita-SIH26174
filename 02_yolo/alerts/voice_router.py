"""One TTS facade over cached WAV / SAPI5 / Piper with a startup-only probe.

The router exposes the same load/synthesize/close boundary AlertManager has
always used, so procedure logic never sees which backend produced audio.
"""

import sys
from dataclasses import replace
from typing import Any

from yolo.alerts.piper_tts import PiperTTS, VoicePolicyBlocked, VoiceUnavailable
from yolo.alerts.sapi5 import Sapi5TTS
from yolo.alerts.voice_cache import CachedWavTTS, CacheMiss

BACKENDS = ("cached_wav", "sapi5", "piper")


def auto_order(platform=None):
    # Windows: verified pre-generated audio, then local OS speech; Piper only if
    # its native phonemizer passed the startup probe. Elsewhere Piper leads.
    if (platform or sys.platform) == "win32":
        return ("cached_wav", "sapi5", "piper")
    return ("piper", "cached_wav", "sapi5")


class VoiceRouter:
    def __init__(self, backends, order, *, explicit=None):
        self.backends = dict(backends)
        self.order = tuple(order)
        self.explicit = explicit
        self.ready: tuple[str, ...] = ()
        self.loaded: list[Any] = []
        self._summary: dict[str, Any] = {
            "mode": explicit or "auto",
            "backends": {name: "PROBING" for name in self.order},
            "ready_order": [],
            "dynamic": None,
            "reasons": {},
            "details": {},
        }

    def load(self):
        if self.ready:
            return
        statuses: dict[str, str] = {}
        reasons: dict[str, str] = {}
        details: dict[str, Any] = {}
        ready: list[str] = []
        for name in self.order:
            backend = self.backends.get(name)
            if backend is None:
                statuses[name] = "NOT_CONFIGURED"
                continue
            try:
                self.loaded.append(backend)
                backend.load()
                if hasattr(backend, "probe"):
                    backend.probe()
                statuses[name] = "READY"
                ready.append(name)
            except VoicePolicyBlocked as exc:
                statuses[name], reasons[name] = "BLOCKED_POLICY", str(exc)
            except Exception as exc:  # noqa: BLE001 -- probe failure disables backend
                statuses[name], reasons[name] = "UNAVAILABLE", str(exc)
            if hasattr(backend, "details") and backend.details():
                details[name] = backend.details()
        self.ready = tuple(ready)
        self._summary = {
            "mode": self.explicit or "auto",
            "backends": statuses,
            "ready_order": list(self.ready),
            "dynamic": next((n for n in self.ready if n != "cached_wav"), None),
            "reasons": reasons,
            "details": details,
        }
        if not self.ready:
            name = self.explicit or "any local backend"
            raise VoiceUnavailable(
                f"requested voice backend {name} unavailable: "
                + "; ".join(f"{k}={v}" for k, v in statuses.items())
                + "".join(f" | {k}: {v}" for k, v in reasons.items())
            )

    def summary(self):
        return self._summary

    def synthesize(self, message):
        failure: Exception | None = None
        for name in self.ready:
            try:
                return replace(self.backends[name].synthesize(message), source=name)
            except CacheMiss as exc:
                failure = failure or exc
            except Exception as exc:  # noqa: BLE001 -- try the next local backend
                failure = exc
        raise VoiceUnavailable(f"no ready voice backend produced audio: {failure}")

    def close(self):
        for backend in self.loaded:
            try:
                backend.close()
            except Exception:  # noqa: BLE001,S110 -- best-effort optional cleanup
                pass
        self.loaded, self.ready = [], ()


def build_voice_router(config, definition, *, platform=None):
    backends = {
        "cached_wav": CachedWavTTS(config.cache_manifest, definition)
        if config.cache_manifest is not None
        else None,
        "sapi5": Sapi5TTS(config.sapi_voice),
        "piper": PiperTTS(config.model_path) if config.model_path is not None else None,
    }
    if config.backend == "auto":
        return VoiceRouter(backends, auto_order(platform))
    return VoiceRouter(backends, (config.backend,), explicit=config.backend)
