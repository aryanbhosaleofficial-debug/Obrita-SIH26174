"""Maintained Piper Python API, guarded local English assets; no download calls."""

import io
import json
import wave
from pathlib import Path

from yolo.alerts.audio_cache import AudioClip


class VoiceUnavailable(RuntimeError):
    pass


class VoicePolicyBlocked(VoiceUnavailable):
    """An OS code-integrity policy refused a native voice component."""


def _policy_block(exc):
    return getattr(exc, "winerror", None) == 4551 or "Application Control" in str(exc)


class PiperTTS:
    name = "piper"

    def __init__(self, model_path):
        self.model_path = Path(model_path) if model_path is not None else None
        self.voice = None

    def load(self):
        if self.voice is not None:
            return
        model = self.model_path
        if model is None or model.suffix.lower() != ".onnx" or not model.is_file():
            raise VoiceUnavailable(
                "configure an existing local .onnx voice using --piper-model"
            )
        config = Path(str(model) + ".json")
        if not config.is_file() or config.stat().st_size > 1024 * 1024:
            raise VoiceUnavailable(
                "Piper requires matching local .onnx.json voice configuration"
            )
        data = json.loads(config.read_text(encoding="utf-8"))
        # Other language frontends may fetch auxiliary models. This initial
        # assistant supports bundled eSpeak English phonemization only.
        if data.get("phoneme_type", "espeak") != "espeak" or not str(
            data.get("espeak", {}).get("voice", "")
        ).startswith("en"):
            raise VoiceUnavailable(
                "offline assistant requires an English eSpeak Piper voice"
            )
        try:
            from piper import PiperVoice
        except ImportError as exc:
            raise VoiceUnavailable(
                "install optional requirements-voice.txt during setup"
            ) from exc
        self.voice = PiperVoice.load(
            str(model), config_path=str(config), use_cuda=False
        )

    def probe(self):
        """One startup phonemizer check; the native eSpeak bridge loads lazily."""
        self.load()
        assert self.voice is not None
        try:
            self.voice.phonemize("ready")
        except (ImportError, OSError) as exc:
            if _policy_block(exc):
                raise VoicePolicyBlocked(
                    f"Piper eSpeak bridge blocked by Windows Application Control: {exc}"
                ) from exc
            raise VoiceUnavailable(f"Piper phonemizer unavailable: {exc}") from exc

    def synthesize(self, message):
        self.load()
        assert self.voice is not None
        buffer = io.BytesIO()
        with wave.open(buffer, "wb") as wav:
            # Initialize the header before phonemization so wave.close() cannot
            # mask a blocked native DLL / synthesis exception with a header error.
            wav.setnchannels(1)
            wav.setsampwidth(2)
            wav.setframerate(self.voice.config.sample_rate)
            self.voice.synthesize_wav(message, wav)
        buffer.seek(0)
        with wave.open(buffer, "rb") as wav:
            if wav.getsampwidth() != 2 or wav.getcomptype() != "NONE":
                raise VoiceUnavailable("Piper must produce uncompressed PCM16")
            return AudioClip(
                wav.readframes(wav.getnframes()), wav.getframerate(), wav.getnchannels()
            )

    def close(self):
        self.voice = None
