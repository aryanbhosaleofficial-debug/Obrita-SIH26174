"""Pre-generated WAV cache: verified manifest, playback-only at runtime.

The manifest maps stable procedure keys (step_id/KIND) to the exact message
text and a WAV file. Text must match what the loaded procedure would speak, so
a cache generated for an older procedure revision is never played.
"""

import hashlib
import io
import json
import re
import wave
from pathlib import Path

import numpy as np
from yolo.alerts.audio_cache import AudioClip
from yolo.alerts.messages import message_entries
from yolo.alerts.piper_tts import VoiceUnavailable

FORMAT = "orbita-voice-cache/1"
MAX_MANIFEST_BYTES = 1024 * 1024
MAX_ENTRIES = 1024
MAX_WAV_BYTES = 16 * 1024 * 1024
_FILE_NAME = re.compile(r"[A-Za-z0-9_-]{1,64}\.wav")


class CacheManifestError(ValueError):
    pass


class CacheMiss(VoiceUnavailable):
    pass


def decode_wav(data, source="cached_wav"):
    try:
        with wave.open(io.BytesIO(data), "rb") as wav:
            if wav.getcomptype() != "NONE" or wav.getsampwidth() != 2:
                raise CacheManifestError("WAV must be uncompressed PCM16")
            clip = AudioClip(
                wav.readframes(wav.getnframes()),
                wav.getframerate(),
                wav.getnchannels(),
                source,
            )
    except (wave.Error, EOFError) as exc:
        raise CacheManifestError(f"corrupt WAV: {exc}") from exc
    except ValueError as exc:
        raise CacheManifestError(str(exc)) from exc
    samples = np.frombuffer(clip.pcm, dtype="<i2")
    if not np.any(np.abs(samples.astype(np.int32)) >= 64):
        raise CacheManifestError("WAV contains no audible PCM")
    return clip


def encode_wav(clip):
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as wav:
        wav.setnchannels(clip.channels)
        wav.setsampwidth(2)
        wav.setframerate(clip.sample_rate)
        wav.writeframes(clip.pcm)
    return buffer.getvalue()


def _no_duplicate_keys(pairs):
    keys = [k for k, _ in pairs]
    if len(keys) != len(set(keys)):
        raise CacheManifestError("manifest contains duplicate keys")
    return dict(pairs)


def load_manifest(path, definition):
    """Return ({text: AudioClip}, report). Bad entries are rejected individually."""
    path = Path(path)
    try:
        if path.stat().st_size > MAX_MANIFEST_BYTES:
            raise CacheManifestError("manifest exceeds 1 MiB")
        data = json.loads(
            path.read_text(encoding="utf-8"), object_pairs_hook=_no_duplicate_keys
        )
    except OSError as exc:
        raise CacheManifestError(f"manifest unreadable: {exc}") from exc
    except json.JSONDecodeError as exc:
        raise CacheManifestError(f"manifest is not JSON: {exc}") from exc
    if (
        not isinstance(data, dict)
        or data.get("format") != FORMAT
        or not isinstance(data.get("entries"), dict)
    ):
        raise CacheManifestError(f"manifest format must be {FORMAT} with entries")
    if data.get("experiment") != definition.name:
        raise CacheManifestError(
            f"manifest is for experiment {data.get('experiment')!r}, "
            f"not {definition.name!r}"
        )
    if len(data["entries"]) > MAX_ENTRIES:
        raise CacheManifestError("manifest has too many entries")
    expected = {key: text for key, _, text in message_entries(definition)}
    clips: dict[str, AudioClip] = {}
    rejected: dict[str, str] = {}
    for key, entry in data["entries"].items():
        try:
            if key not in expected:
                raise CacheManifestError("key is not a message of this procedure")
            if not isinstance(entry, dict) or not all(
                isinstance(entry.get(f), str) for f in ("text", "file", "sha256")
            ):
                raise CacheManifestError("entry requires text, file and sha256")
            if entry["text"] != expected[key]:
                raise CacheManifestError("stale text; regenerate the cache")
            if not _FILE_NAME.fullmatch(entry["file"]):
                raise CacheManifestError("file must be a plain local .wav name")
            wav_path = path.parent / entry["file"]
            if not wav_path.is_file():
                raise CacheManifestError("WAV file missing")
            if wav_path.stat().st_size > MAX_WAV_BYTES:
                raise CacheManifestError("WAV file too large")
            raw = wav_path.read_bytes()
            if hashlib.sha256(raw).hexdigest() != entry["sha256"].lower():
                raise CacheManifestError("WAV sha256 mismatch")
            clips.setdefault(entry["text"], decode_wav(raw))
        except (CacheManifestError, OSError) as exc:
            rejected[key] = str(exc)
    report = {
        "manifest": str(path),
        "generator": data.get("generator"),
        "valid_entries": len(data["entries"]) - len(rejected),
        "rejected": rejected,
        "missing_keys": sorted(set(expected) - set(data["entries"])),
    }
    return clips, report


def write_cache(definition, synthesize, output_dir, generator):
    """Synthesize every fixed procedure message into output_dir (tool-side only)."""
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    entries, written = {}, {}
    for key, kind, text in message_entries(definition):
        if text not in written:
            raw = encode_wav(synthesize(text))
            name = hashlib.sha256(text.encode("utf-8")).hexdigest()[:24] + ".wav"
            (output_dir / name).write_bytes(raw)
            written[text] = (name, hashlib.sha256(raw).hexdigest())
        name, digest = written[text]
        entries[key] = {"kind": kind, "text": text, "file": name, "sha256": digest}
    manifest = {
        "format": FORMAT,
        "experiment": definition.name,
        "generator": generator,
        "entries": entries,
    }
    path = output_dir / "manifest.json"
    path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False), "utf-8")
    return path


class CachedWavTTS:
    """Playback-only backend: never synthesizes, only returns verified PCM."""

    name = "cached_wav"

    def __init__(self, manifest_path, definition):
        self.manifest_path = manifest_path
        self.definition = definition
        self.clips = None
        self.report = None

    def load(self):
        if self.clips is not None:
            return
        if self.manifest_path is None:
            raise VoiceUnavailable("no voice cache manifest configured")
        try:
            clips, self.report = load_manifest(self.manifest_path, self.definition)
        except CacheManifestError as exc:
            raise VoiceUnavailable(f"voice cache rejected: {exc}") from exc
        if not clips:
            raise VoiceUnavailable("voice cache has no valid entries for procedure")
        self.clips = clips

    def details(self):
        if self.report is None:
            return None
        return {
            "valid_entries": self.report["valid_entries"],
            "rejected_entries": len(self.report["rejected"]),
            "missing_keys": len(self.report["missing_keys"]),
            "generator": self.report["generator"],
        }

    def synthesize(self, message):
        clip = (self.clips or {}).get(message)
        if clip is None:
            raise CacheMiss("message not in voice cache")
        return clip

    def close(self):
        self.clips = None
