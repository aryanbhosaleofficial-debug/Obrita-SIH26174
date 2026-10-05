"""Local Windows SAPI5 speech rendered to in-memory PCM (no cloud, no files).

SAPI writes into an SpMemoryStream; playback, preemption and onset timing stay
on the shared PortAudio worker. COM objects live on the single voice-worker
thread that calls load(), synthesize() and close().
"""

import sys
from threading import get_ident

import numpy as np
from yolo.alerts.audio_cache import AudioClip
from yolo.alerts.piper_tts import VoiceUnavailable

SAMPLE_RATE = 22050
_SAFT22KHZ16BITMONO = 22
_SVSF_IS_NOT_XML = 16  # speak procedure text literally, never as SAPI XML
_LEAD_S, _TAIL_S = 0.02, 0.15


def trim_silence(pcm, sample_rate, threshold=64):
    samples = np.frombuffer(pcm, dtype="<i2")
    audible = np.flatnonzero(np.abs(samples.astype(np.int32)) >= threshold)
    if not len(audible):
        raise VoiceUnavailable("SAPI5 produced no audible PCM")
    start = max(0, int(audible[0]) - int(_LEAD_S * sample_rate))
    end = min(len(samples), int(audible[-1]) + 1 + int(_TAIL_S * sample_rate))
    return samples[start:end].tobytes()


class Sapi5TTS:
    name = "sapi5"

    def __init__(self, voice_name=None):
        self.voice_name = voice_name
        self.voice_description = None
        self._voice = None
        self._client = None
        self._comtypes = None
        self._thread = None

    def load(self):
        if self._voice is not None:
            return
        if sys.platform != "win32":
            raise VoiceUnavailable("SAPI5 requires Windows")
        try:
            import comtypes
            import comtypes.client
        except ImportError as exc:
            raise VoiceUnavailable(
                "SAPI5 needs comtypes from requirements-voice.txt"
            ) from exc
        comtypes.CoInitialize()
        self._comtypes, self._client, self._thread = (
            comtypes,
            comtypes.client,
            get_ident(),
        )
        try:
            voice = self._client.CreateObject("SAPI.SpVoice", dynamic=True)
            if self.voice_name:
                tokens = voice.GetVoices()
                match = next(
                    (
                        tokens.Item(i)
                        for i in range(tokens.Count)
                        if self.voice_name.lower()
                        in str(tokens.Item(i).GetDescription()).lower()
                    ),
                    None,
                )
                if match is None:
                    raise VoiceUnavailable(
                        f"SAPI5 voice not installed: {self.voice_name}"
                    )
                voice.Voice = match
            self.voice_description = str(voice.Voice.GetDescription())
            self._voice = voice
        except VoiceUnavailable:
            self.close()
            raise
        except Exception as exc:
            self.close()
            raise VoiceUnavailable(f"SAPI5 unavailable: {exc}") from exc

    def details(self):
        return {"voice": self.voice_description} if self.voice_description else None

    def synthesize(self, message):
        self.load()
        if get_ident() != self._thread:
            raise RuntimeError("SAPI5 backend is bound to its voice-worker thread")
        assert self._client is not None and self._voice is not None
        audio_format = self._client.CreateObject("SAPI.SpAudioFormat", dynamic=True)
        audio_format.Type = _SAFT22KHZ16BITMONO
        stream = self._client.CreateObject("SAPI.SpMemoryStream", dynamic=True)
        stream.Format = audio_format
        self._voice.AudioOutputStream = stream  # fresh stream per message
        self._voice.Speak(message, _SVSF_IS_NOT_XML)
        data = stream.GetData()
        pcm = data if isinstance(data, bytes) else bytes(bytearray(data))
        return AudioClip(trim_silence(pcm, SAMPLE_RATE), SAMPLE_RATE, 1, self.name)

    def close(self):
        self._voice = None
        if self._comtypes is not None and self._thread == get_ident():
            self._comtypes.CoUninitialize()
        self._comtypes = self._client = None
