"""Multi-backend voice: mocked COM/Piper/audio boundaries, never real speech."""

import hashlib
import importlib.util
import json
import sys
import time
from pathlib import Path
from threading import get_ident
from types import SimpleNamespace

import numpy as np
import pytest
from yolo.alerts.audio_cache import AudioClip
from yolo.alerts.contracts import AlertEvent, VoiceConfig
from yolo.alerts.manager import AlertManager
from yolo.alerts.messages import message_entries, procedure_messages
from yolo.alerts.piper_tts import PiperTTS, VoicePolicyBlocked, VoiceUnavailable
from yolo.alerts.sapi5 import Sapi5TTS, trim_silence
from yolo.alerts.timing import host_time
from yolo.alerts.voice_cache import (
    CachedWavTTS,
    CacheManifestError,
    CacheMiss,
    encode_wav,
    load_manifest,
    write_cache,
)
from yolo.alerts.voice_router import VoiceRouter, auto_order, build_voice_router
from yolo.procedure.assistant import ProcedureAssistant
from yolo.procedure.contracts import ConfirmedAction
from yolo.procedure.markdown_loader import load_procedure
from yolo.semantic.contracts import default_actions
from yolo.visualization.procedure_overlay import render_procedure, voice_backend_line

OWNER = Path(__file__).resolve().parents[1]
SAMPLE = OWNER / "examples/red_yellow_procedure.md"
DEFINITION = load_procedure(SAMPLE)


def tone(seconds=0.2, rate=16000):
    t = np.arange(int(rate * seconds)) / rate
    return AudioClip((3000 * np.sin(2 * np.pi * 440 * t)).astype("<i2").tobytes(), rate)


def build_cache(tmp_path):
    return write_cache(
        DEFINITION, lambda text: tone(), tmp_path / "cache", {"backend": "test"}
    )


class FakeBackend:
    def __init__(self, name, *, fail_load=None, texts=None, delay=0.0):
        self.name, self.fail_load, self.texts, self.delay = (
            name,
            fail_load,
            texts,
            delay,
        )
        self.loads = self.calls = self.closed = 0

    def load(self):
        self.loads += 1
        if self.fail_load:
            raise self.fail_load

    def synthesize(self, text):
        self.calls += 1
        time.sleep(self.delay)
        if self.texts is not None and text not in self.texts:
            raise CacheMiss("miss")
        return tone()

    def close(self):
        self.closed += 1


class Player:
    def __init__(self):
        self.clips = []

    def play(self, clip, on_start, cancel):
        self.clips.append(clip)
        on_start(host_time(), "mock_audio_test_only")


def critical(manager, kind="WRONG_ORDER"):
    step = DEFINITION.steps[0]
    text = {k: t for k, _, t in message_entries(DEFINITION)}[f"{step.step_id}/{kind}"]
    return AlertEvent(kind, text, 1, 1, 1.0, step.step_id, "PICK_YELLOW", host_time())


def wait(manager, predicate, timeout=3):
    with manager._condition:
        assert manager._condition.wait_for(predicate, timeout=timeout)


# ---------------------------------------------------------------- messages


def test_message_keys_are_stable_and_critical_first():
    entries = message_entries(DEFINITION)
    keys = [k for k, _, _ in entries]
    assert len(keys) == len(set(keys))
    assert "pick_red/WRONG_ORDER" in keys and "_procedure/COMPLETED" in keys
    kinds = [kind for _, kind, _ in entries]
    first_prompt = kinds.index("NEXT_STEP")
    assert set(kinds[:first_prompt]) <= {
        "SKIPPED_STEP",
        "WRONG_ORDER",
        "UNEXPECTED_ACTION",
    }
    texts = procedure_messages(DEFINITION, VoiceConfig())
    assert "Procedure complete." in texts and "Correct. Continue." not in texts
    assert "Wrong order. Pick up the red box." in texts


# ---------------------------------------------------------------- cache


def test_cache_roundtrip_dedupes_audio_and_validates(tmp_path):
    manifest = build_cache(tmp_path)
    data = json.loads(manifest.read_text(encoding="utf-8"))
    assert data["generator"] == {"backend": "test"}
    clips, report = load_manifest(manifest, DEFINITION)
    assert report["rejected"] == {} and report["missing_keys"] == []
    assert len(clips) == len({e["text"] for e in data["entries"].values()})
    backend = CachedWavTTS(manifest, DEFINITION)
    backend.load()
    clip = backend.synthesize("Wrong order. Pick up the red box.")
    assert clip.source == "cached_wav" and clip.sample_rate == 16000
    with pytest.raises(CacheMiss):
        backend.synthesize("Not a procedure message.")


@pytest.mark.parametrize(
    "damage, reason",
    [
        ("missing", "WAV file missing"),
        ("corrupt", "corrupt WAV"),
        ("sha", "sha256 mismatch"),
        ("stale", "stale text"),
        ("traversal", "plain local .wav"),
        ("unknown", "not a message of this procedure"),
        ("silent", "no audible PCM"),
    ],
)
def test_cache_rejects_bad_entries_individually(tmp_path, damage, reason):
    manifest = build_cache(tmp_path)
    data = json.loads(manifest.read_text(encoding="utf-8"))
    key = "manipulate_red/SKIPPED_STEP"
    entry = data["entries"][key]
    wav = manifest.parent / entry["file"]
    if damage == "missing":
        wav.unlink()
    elif damage == "corrupt":
        wav.write_bytes(b"RIFF....not a wav")
        entry["sha256"] = hashlib.sha256(wav.read_bytes()).hexdigest()
    elif damage == "sha":
        entry["sha256"] = "0" * 64
    elif damage == "stale":
        entry["text"] = "Old wording."
    elif damage == "traversal":
        entry["file"] = "../outside.wav"
    elif damage == "unknown":
        data["entries"]["ghost_step/WRONG_ORDER"] = data["entries"].pop(key)
        key = "ghost_step/WRONG_ORDER"
    elif damage == "silent":
        silent = encode_wav(AudioClip(b"\x00\x00" * 1600, 16000))
        (manifest.parent / "silent.wav").write_bytes(silent)
        entry.update(file="silent.wav", sha256=hashlib.sha256(silent).hexdigest())
    manifest.write_text(json.dumps(data), encoding="utf-8")
    clips, report = load_manifest(manifest, DEFINITION)
    assert reason in report["rejected"][key]
    assert len(report["rejected"]) == 1  # one bad file does not invalidate others
    assert "Wrong order. Pick up the red box." in clips


def test_cache_rejects_whole_manifest_for_duplicates_or_other_experiment(tmp_path):
    manifest = build_cache(tmp_path)
    text = manifest.read_text(encoding="utf-8")
    first = text.index('"pick_red/SKIPPED_STEP"')
    duplicate = text[:first] + '"pick_red/WRONG_ORDER": {}, ' + text[first:]
    manifest.write_text(duplicate, encoding="utf-8")
    with pytest.raises(CacheManifestError, match="duplicate"):
        load_manifest(manifest, DEFINITION)
    data = json.loads(text)
    data["experiment"] = "Another Experiment"
    manifest.write_text(json.dumps(data), encoding="utf-8")
    with pytest.raises(CacheManifestError, match="Another Experiment"):
        load_manifest(manifest, DEFINITION)
    with pytest.raises(VoiceUnavailable, match="rejected"):
        CachedWavTTS(manifest, DEFINITION).load()
    with pytest.raises(VoiceUnavailable, match="no voice cache"):
        CachedWavTTS(None, DEFINITION).load()


# ---------------------------------------------------------------- router


def test_auto_order_is_platform_deterministic():
    assert auto_order("win32") == ("cached_wav", "sapi5", "piper")
    assert auto_order("linux") == ("piper", "cached_wav", "sapi5")
    router = build_voice_router(VoiceConfig(), DEFINITION, platform="win32")
    assert router.order == ("cached_wav", "sapi5", "piper")
    assert router.backends["cached_wav"] is None and router.backends["piper"] is None
    explicit = build_voice_router(VoiceConfig(backend="piper"), DEFINITION)
    assert explicit.order == ("piper",) and explicit.explicit == "piper"


def test_auto_probes_once_and_never_retries_blocked_piper_per_message():
    cached = FakeBackend("cached_wav", texts={"A."})
    sapi = FakeBackend("sapi5")
    piper = FakeBackend(
        "piper", fail_load=VoicePolicyBlocked("Application Control blocked")
    )
    router = VoiceRouter(
        {"cached_wav": cached, "sapi5": sapi, "piper": piper},
        ("cached_wav", "sapi5", "piper"),
    )
    router.load()
    router.load()
    assert router.summary()["backends"] == {
        "cached_wav": "READY",
        "sapi5": "READY",
        "piper": "BLOCKED_POLICY",
    }
    assert router.summary()["dynamic"] == "sapi5"
    assert router.synthesize("A.").source == "cached_wav"
    assert router.synthesize("B.").source == "sapi5"  # cache miss -> SAPI5
    assert piper.loads == 1 and piper.calls == 0
    router.close()
    assert cached.closed == sapi.closed == 1


def test_explicit_backend_never_falls_back():
    sapi = FakeBackend("sapi5")
    router = VoiceRouter(
        {
            "piper": FakeBackend("piper", fail_load=VoicePolicyBlocked("blocked")),
            "sapi5": sapi,
        },
        ("piper",),
        explicit="piper",
    )
    with pytest.raises(VoiceUnavailable, match="requested voice backend piper"):
        router.load()
    assert router.summary()["backends"] == {"piper": "BLOCKED_POLICY"}
    assert sapi.loads == 0
    missing = VoiceRouter({"piper": None}, ("piper",), explicit="piper")
    with pytest.raises(VoiceUnavailable, match="NOT_CONFIGURED"):
        missing.load()


def test_piper_probe_classifies_application_control_block(tmp_path):
    class Voice:
        error = ImportError(
            "DLL load failed while importing espeakbridge: "
            "An Application Control policy has blocked this file."
        )

        def phonemize(self, text):
            raise self.error

    piper = PiperTTS(None)
    piper.voice = Voice()
    with pytest.raises(VoicePolicyBlocked):
        piper.probe()
    Voice.error = ImportError("espeak data missing")
    with pytest.raises(VoiceUnavailable) as info:
        piper.probe()
    assert not isinstance(info.value, VoicePolicyBlocked)


# ---------------------------------------------------------------- SAPI5


def fake_comtypes(monkeypatch, *, voices=("Microsoft David", "Microsoft Zira")):
    calls = SimpleNamespace(init=0, uninit=0, speak=[], created=[])
    pcm = np.concatenate(
        [
            np.zeros(4410, "<i2"),
            (np.ones(2205) * 5000).astype("<i2"),
            np.zeros(22050, "<i2"),
        ]
    ).tobytes()

    class Token:
        def __init__(self, name):
            self.name = name

        def GetDescription(self):
            return self.name

    class Tokens:
        Count = len(voices)

        def Item(self, i):
            return Token(voices[i])

    class Stream:
        Format = None

        def GetData(self):
            return list(pcm)

    class Voice:
        def __init__(self):
            self.Voice = Token(voices[0])
            self.AudioOutputStream = None

        def GetVoices(self):
            return Tokens()

        def Speak(self, text, flags):
            assert isinstance(self.AudioOutputStream, Stream)
            calls.speak.append((text, flags))

    def create(progid, dynamic=False):
        calls.created.append(progid)
        return {"SAPI.SpVoice": Voice, "SAPI.SpMemoryStream": Stream}.get(
            progid, SimpleNamespace
        )()

    def init():
        calls.init += 1

    def uninit():
        calls.uninit += 1

    client = SimpleNamespace(CreateObject=create)
    module = SimpleNamespace(CoInitialize=init, CoUninitialize=uninit, client=client)
    monkeypatch.setitem(sys.modules, "comtypes", module)
    monkeypatch.setitem(sys.modules, "comtypes.client", client)
    monkeypatch.setattr(sys, "platform", "win32")
    return calls


def test_sapi5_renders_literal_text_to_trimmed_memory_pcm(monkeypatch):
    calls = fake_comtypes(monkeypatch)
    sapi = Sapi5TTS("zira")
    sapi.load()
    assert sapi.voice_description == "Microsoft Zira"
    clip = sapi.synthesize("Wrong <order> & text.")
    assert calls.speak == [("Wrong <order> & text.", 16)]  # SVSFIsNotXML
    assert clip.source == "sapi5" and clip.sample_rate == 22050
    duration = len(clip.pcm) / 2 / 22050
    assert duration == pytest.approx(0.02 + 0.1 + 0.15, abs=0.01)  # 200 ms lead trimmed
    sapi.close()
    assert calls.init == calls.uninit == 1


def test_sapi5_failures_are_voice_unavailable(monkeypatch):
    fake_comtypes(monkeypatch)
    with pytest.raises(VoiceUnavailable, match="not installed"):
        Sapi5TTS("hazel").load()
    monkeypatch.setitem(sys.modules, "comtypes", None)
    with pytest.raises(VoiceUnavailable, match="comtypes"):
        Sapi5TTS().load()
    monkeypatch.setattr(sys, "platform", "linux")
    with pytest.raises(VoiceUnavailable, match="requires Windows"):
        Sapi5TTS().load()
    with pytest.raises(VoiceUnavailable):
        trim_silence(b"\x00\x00" * 100, 22050)


def test_sapi5_is_bound_to_the_voice_worker_thread(monkeypatch):
    fake_comtypes(monkeypatch)
    sapi = Sapi5TTS()
    sapi.load()
    sapi._thread = get_ident() + 1
    with pytest.raises(RuntimeError, match="voice-worker thread"):
        sapi.synthesize("Hello.")


# ---------------------------------------------------------------- manager


def manager_with(backends, order, config=None):
    router = VoiceRouter(backends, order)
    return AlertManager(
        DEFINITION, config or VoiceConfig(), tts=router, player=Player()
    )


def test_manager_uses_cache_for_critical_and_sapi_for_the_rest(tmp_path):
    manifest = build_cache(tmp_path)
    data = json.loads(manifest.read_text(encoding="utf-8"))
    # Simulate an incomplete cache: only critical warnings were pre-generated.
    data["entries"] = {k: v for k, v in data["entries"].items() if "NEXT_STEP" not in k}
    manifest.write_text(json.dumps(data), encoding="utf-8")
    sapi = FakeBackend("sapi5")
    manager = manager_with(
        {"cached_wav": CachedWavTTS(manifest, DEFINITION), "sapi5": sapi},
        ("cached_wav", "sapi5"),
    )
    try:
        wait(manager, lambda: manager._status == "READY")
        status = manager.backend_status
        prompts = len(DEFINITION.steps)
        assert status["fixed_messages"]["sapi5"] == prompts  # only NEXT_STEP missed
        assert status["fixed_messages"]["cached_wav"] > prompts
        assert manager.enqueue(critical(manager))
        wait(manager, lambda: not manager._queue and manager._active is None)
        assert manager.player.clips[-1].source == "cached_wav"
    finally:
        manager.close()


def test_preload_miss_skips_only_that_message_and_dynamic_uses_fallback():
    cached = FakeBackend("cached_wav", texts={"Wrong order. Pick up the red box."})
    manager = manager_with({"cached_wav": cached}, ("cached_wav",))
    try:
        wait(manager, lambda: manager._status == "READY")
        assert manager.backend_status["fixed_messages"] == {"cached_wav": 1}
        assert manager.enqueue(critical(manager))
        wait(manager, lambda: not manager._queue and manager._active is None)
        assert manager.player.clips[-1].source == "cached_wav"
    finally:
        manager.close()


def test_enqueue_never_waits_for_slow_dynamic_synthesis():
    sapi = FakeBackend("sapi5")
    manager = manager_with(
        {"sapi5": sapi}, ("sapi5",), VoiceConfig(speak_next_step=False)
    )
    try:
        wait(manager, lambda: manager._status == "READY")
        sapi.delay = 0.4  # slow runtime synthesis only
        manager.cache.clear()  # force runtime synthesis on the worker
        started = time.perf_counter()
        assert manager.enqueue(critical(manager))
        assert (time.perf_counter() - started) < 0.05
        wait(manager, lambda: not manager._queue and manager._active is None)
        assert manager.player.clips[-1].source == "sapi5"
    finally:
        manager.close()


def test_no_backend_means_voice_unavailable_but_procedure_continues():
    router = VoiceRouter(
        {
            "cached_wav": None,
            "sapi5": FakeBackend("sapi5", fail_load=VoiceUnavailable("no COM")),
            "piper": FakeBackend("piper", fail_load=VoicePolicyBlocked("blocked")),
        },
        ("cached_wav", "sapi5", "piper"),
    )
    assistant = ProcedureAssistant(
        DEFINITION,
        default_actions(),
        voice_config=VoiceConfig(),
        tts=router,
        player=Player(),
    )
    try:
        wait(assistant.alerts, lambda: assistant.alerts._status == "VOICE_UNAVAILABLE")
        assistant.accept_confirmed(
            ConfirmedAction(
                "PICK_YELLOW", "yellow_box", 1, 0.0, "injected", host_time()
            )
        )
        assert assistant.state.status == "WRONG_ORDER"
        assert assistant.state.current_step_index == 0
        line = voice_backend_line(assistant.alerts.backend_status)
        assert "PIPER: BLOCKED_POLICY" in line and "Dynamic: NONE" in line
    finally:
        assistant.close()


def test_hud_reports_backends_truthfully_without_mutating_input():
    display = np.zeros((120, 160, 3), np.uint8)
    summary = {
        "backends": {
            "cached_wav": "READY",
            "sapi5": "READY",
            "piper": "BLOCKED_POLICY",
        },
        "dynamic": "sapi5",
        "fixed_messages": {"cached_wav": 21, "sapi5": 1},
    }
    line = voice_backend_line(summary)
    assert (
        line == "Fixed: CACHED_WAV 21, SAPI5 1 | Dynamic: SAPI5 | PIPER: BLOCKED_POLICY"
    )
    before = display.copy()
    state = SimpleNamespace(
        current_step_index=0,
        total_steps=5,
        status="ACTIVE",
        next_action="PICK_RED",
        last_action="NONE",
        next_instruction="Pick up the red box.",
    )
    output = render_procedure(
        display, state, voice_status="READY", voice_backends=summary
    )
    assert np.array_equal(display, before) and output.shape[0] > display.shape[0]
    assert voice_backend_line(None) is None


def test_voice_config_and_cli_validate_backend_options(tmp_path):
    with pytest.raises(ValueError, match="voice.backend"):
        VoiceConfig(backend="cloud")
    with pytest.raises(ValueError, match="sapi_voice"):
        VoiceConfig(sapi_voice="")
    from yolo.standalone_cli import main

    image = tmp_path / "x.png"
    image.write_bytes(b"")
    assert (
        main(["--source", str(image), "--voice-backend", "sapi5", "--no-display"]) == 2
    )


def test_build_tool_writes_verified_manifest_with_generator_label(
    tmp_path, monkeypatch
):
    spec = importlib.util.spec_from_file_location(
        "build_voice_cache", OWNER / "tools/build_voice_cache.py"
    )
    tool = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(tool)

    class FakeSapi(FakeBackend):
        voice_description = "Fake Voice"

        def __init__(self, voice_name=None):
            super().__init__("sapi5")

    monkeypatch.setattr(tool, "Sapi5TTS", FakeSapi)
    output = tmp_path / "cache"
    code = tool.main(
        ["--procedure", str(SAMPLE), "--backend", "sapi5", "--output", str(output)]
    )
    assert code == 0
    data = json.loads((output / "manifest.json").read_text(encoding="utf-8"))
    assert data["generator"] == {"backend": "sapi5", "voice": "Fake Voice"}
    assert set(data["entries"]) == {k for k, _, _ in message_entries(DEFINITION)}
