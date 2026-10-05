"""Mocked Piper/audio boundaries: these timings are NOT the real speaker benchmarks."""

import json
import sys
from pathlib import Path
from threading import Event
from time import monotonic
from types import SimpleNamespace

import numpy as np
import pytest
from yolo.adapters.standalone import adapt_image
from yolo.alerts.audio_cache import AudioCache, AudioClip
from yolo.alerts.contracts import AlertEvent, VoiceConfig
from yolo.alerts.manager import AlertManager, step_message
from yolo.alerts.piper_tts import PiperTTS, VoiceUnavailable
from yolo.alerts.playback import SoundDevicePlayback
from yolo.alerts.timing import host_time
from yolo.core.contracts import BoundingBox, Detection, DetectorConfig
from yolo.core.pipeline import DetectorPipeline
from yolo.procedure.assistant import ProcedureAssistant
from yolo.procedure.contracts import ConfirmedAction
from yolo.procedure.event_log import EventLog
from yolo.procedure.fast_actions import FastConfig, HomeRegion
from yolo.procedure.markdown_loader import load_procedure
from yolo.semantic.contracts import (
    SemanticConfig,
    SemanticResult,
    SemanticStatus,
    default_actions,
)

SAMPLE = Path(__file__).resolve().parents[1] / "examples/red_yellow_procedure.md"


class FakeTTS:
    def __init__(self):
        self.loaded = 0
        self.messages = []
        self.closed = 0

    def load(self):
        self.loaded += 1

    def synthesize(self, message):
        self.messages.append(message)
        return AudioClip(b"\x00\x10" * 800, 8000)

    def close(self):
        self.closed += 1


class FakePlayer:
    def __init__(self, clock=host_time):
        self.clips = []
        self.clock = clock

    def play(self, clip, on_start, cancel):
        self.clips.append(clip)
        on_start(self.clock(), "mock_audio_test_only")


def wait_ready(manager):
    with manager._condition:
        assert manager._condition.wait_for(
            lambda: manager.status != "WARMING", timeout=3
        )
    assert manager.status == "READY"


def wait_idle(manager):
    with manager._condition:
        assert manager._condition.wait_for(
            lambda: not manager._queue and manager._active is None, timeout=3
        )


def warning(manager, frame=1, observed="PLACE_RED"):
    step = load_procedure(SAMPLE).steps[1]
    return AlertEvent(
        "SKIPPED_STEP",
        step_message(step, "SKIPPED_STEP"),
        1,
        frame,
        float(frame),
        step.step_id,
        observed,
        manager.clock(),
    )


def test_preload_once_presynthesis_cached_playback_and_instrumentation():
    tts, player, records = FakeTTS(), FakePlayer(), []
    manager = AlertManager(
        load_procedure(SAMPLE), tts=tts, player=player, emit=records.append
    )
    try:
        wait_ready(manager)
        assert tts.loaded == 1 and len(tts.messages) == len(set(manager.messages))
        assert all(
            manager.cache.get(message) is not None for message in manager.messages
        )
        before = len(tts.messages)
        assert manager.enqueue(warning(manager))
        wait_idle(manager)
        assert len(tts.messages) == before and len(player.clips) == 1
        record = next(r for r in records if r["event"] == "audio_playback_started")
        assert (
            record["violation_confirmed_timestamp"]
            <= record["alert_queued_timestamp"]
            <= record["audio_playback_start_timestamp"]
        )
        assert (
            record["warning_start_latency_ms"] >= 0 and not record["dynamic_synthesis"]
        )
        assert record["measurement_method"] == "mock_audio_test_only"
    finally:
        manager.close()
    assert tts.closed == 1 and not manager.cache.items


def test_cooldown_duplicate_suppression_and_dynamic_fallback():
    now = [100.0]
    clock = lambda: now[0]
    tts, player = FakeTTS(), FakePlayer(clock)
    manager = AlertManager(load_procedure(SAMPLE), tts=tts, player=player, clock=clock)
    try:
        wait_ready(manager)
        assert manager.enqueue(warning(manager))
        wait_idle(manager)
        assert not manager.enqueue(warning(manager, 2))
        now[0] += 2.6
        assert manager.enqueue(warning(manager, 3))
        wait_idle(manager)
        dynamic = AlertEvent(
            "SMOKE", "Unique uncached phrase.", 3, 4, 4, None, "NONE", clock()
        )
        before = len(tts.messages)
        assert manager.enqueue(dynamic)
        wait_idle(manager)
        assert len(tts.messages) == before + 1
        assert manager.cache.get(dynamic.message) is not None
    finally:
        manager.close()


def test_bounded_priority_queue_and_duplicate_coalescing():
    entered, release = Event(), Event()

    class DelayedTTS(FakeTTS):
        def load(self):
            super().load()
            entered.set()
            assert release.wait(3)

    player = FakePlayer()
    manager = AlertManager(
        load_procedure(SAMPLE),
        VoiceConfig(queue_capacity=2),
        tts=DelayedTTS(),
        player=player,
    )
    try:
        assert entered.wait(3)
        low = AlertEvent(
            "NEXT_STEP", "Next step.", 3, 0, 0, "pick_red", "NONE", monotonic()
        )
        assert manager.enqueue(low)
        high = warning(manager)
        assert manager.enqueue(high)
        assert len(manager._queue) == 1 and manager._queue[0][3] == high
        for _ in range(100):
            assert not manager.enqueue(high)
        assert manager.enqueue(warning(manager, 2, "PICK_YELLOW"))
        assert not manager.enqueue(warning(manager, 3, "MANIPULATE_YELLOW"))
        assert len(manager._queue) == 2
        release.set()
        wait_idle(manager)
        assert len(player.clips) == 2
    finally:
        release.set()
        manager.close()


def test_priority_error_cancels_active_information_on_same_worker():
    entered = Event()

    class Player(FakePlayer):
        def play(self, clip, on_start, cancel):
            super().play(clip, on_start, cancel)
            if len(self.clips) == 1:
                entered.set()
                assert cancel.wait(3)

    player = Player()
    manager = AlertManager(load_procedure(SAMPLE), tts=FakeTTS(), player=player)
    try:
        wait_ready(manager)
        manager.enqueue(
            AlertEvent(
                "NEXT_STEP", "Next step.", 3, 0, 0, "pick_red", "NONE", monotonic()
            )
        )
        assert entered.wait(3)
        assert manager.enqueue(warning(manager))
        wait_idle(manager)
        assert len(player.clips) == 2
        assert manager._thread.is_alive()
    finally:
        manager.close()


def test_reset_rejects_stale_audio_callback_and_clears_pending_state():
    entered, release = Event(), Event()
    records = []

    class DelayedPlayer(FakePlayer):
        def play(self, clip, on_start, cancel):
            entered.set()
            assert release.wait(3)
            on_start(monotonic(), "mock_audio_test_only")

    manager = AlertManager(
        load_procedure(SAMPLE),
        tts=FakeTTS(),
        player=DelayedPlayer(),
        emit=records.append,
    )
    try:
        wait_ready(manager)
        manager.enqueue(warning(manager))
        assert entered.wait(3)
        manager.reset()
        release.set()
        wait_idle(manager)
        assert manager.last_latency_ms is None and not manager._cooldown
        assert not any(r["event"] == "audio_playback_started" for r in records)
    finally:
        release.set()
        manager.close()


def test_f5_reset_active_prompt_accepts_same_new_generation_prompt():
    entered, release = Event(), Event()
    records = []

    class HoldingPlayer(FakePlayer):
        def play(self, clip, on_start, cancel):
            self.clips.append(clip)
            if len(self.clips) == 1:
                entered.set()
                assert cancel.wait(3)
                assert release.wait(3)
            on_start(self.clock(), "mock_audio_test_only")

    player = HoldingPlayer()
    manager = AlertManager(
        load_procedure(SAMPLE), tts=FakeTTS(), player=player, emit=records.append
    )
    try:
        wait_ready(manager)
        prompt = AlertEvent(
            "NEXT_STEP", "Next step.", 3, 1, 1, "pick_red", "NONE", host_time()
        )
        assert manager.enqueue(prompt)
        assert entered.wait(3)
        manager.reset()
        assert manager.enqueue(
            prompt
        )  # same key while cancelled player still returning
        release.set()
        wait_idle(manager)
        assert len(player.clips) == 2
        assert len([r for r in records if r["event"] == "audio_playback_started"]) == 1
        assert not any(r.get("reason") == "duplicate_or_cooldown" for r in records)
    finally:
        release.set()
        manager.close()


def test_f4_perf_counter_clock_is_shared_and_injectable(monkeypatch):
    from yolo.alerts import timing
    from yolo.procedure.fusion import ActionConfirmation
    from yolo.procedure.validator import ProcedureValidator

    monkeypatch.setattr(timing, "perf_counter", lambda: 123.456789)
    assert host_time() == 123.456789
    confirmation = ActionConfirmation()
    event = confirmation.observe("PICK_RED", "red_box", 1, 1, 1, "fast")
    assert event.confirmed_monotonic_s == 123.456789
    validator = ProcedureValidator(load_procedure(SAMPLE))
    assert validator.clock is host_time and validator.started_s == 123.456789
    clock = lambda: 5.0
    manager = AlertManager(
        load_procedure(SAMPLE), VoiceConfig(enabled=False), clock=clock
    )
    assert manager.clock is clock and manager.player.clock is clock
    manager.close()


@pytest.mark.parametrize("stage", ["load", "synthesize", "play"])
def test_voice_failures_do_not_break_procedure(stage):
    tts, player = FakeTTS(), FakePlayer()

    def fail(*args):
        raise RuntimeError("injected audio failure")

    if stage == "play":
        player.play = fail
    else:
        setattr(tts, stage, fail)
    assistant = ProcedureAssistant(
        load_procedure(SAMPLE), default_actions(), tts=tts, player=player
    )
    try:
        with assistant.alerts._condition:
            assert assistant.alerts._condition.wait_for(
                lambda: assistant.alerts.status in {"VOICE_UNAVAILABLE", "VOICE_ERROR"},
                timeout=3,
            )
        for i, name in enumerate(("PICK_RED", "MANIPULATE_RED", "PLACE_RED")):
            assert (
                assistant.accept_confirmed(
                    ConfirmedAction(name, "red_box", i, i, "injected_test", monotonic())
                ).event
                == "STEP_COMPLETED"
            )
        assert assistant.state.current_step_index == 3
    finally:
        assistant.close()


def test_voice_disabled_has_no_worker_or_tts_calls():
    tts = FakeTTS()
    manager = AlertManager(load_procedure(SAMPLE), VoiceConfig(enabled=False), tts=tts)
    assert manager.status == "DISABLED" and manager._thread is None and tts.loaded == 0
    assert not manager.enqueue(warning(manager))
    manager.close()


def test_cache_bounds_and_voice_config_validation():
    cache = AudioCache(1, 1600)
    clip = AudioClip(b"\x00\x10" * 800, 8000)
    cache.put("first", clip)
    with pytest.raises(ValueError):
        cache.put("second", clip)
    cache.put("second", clip, evict=True)
    assert cache.get("first") is None and cache.bytes_used == 1600
    for kwargs in (
        {"queue_capacity": 0},
        {"alert_cooldown_ms": -1},
        {"enabled": "true"},
        {"device": -1},
    ):
        with pytest.raises(ValueError):
            VoiceConfig(**kwargs)


def test_piper_actual_api_shape_loads_model_once_with_mocked_local_boundary(
    tmp_path, monkeypatch
):
    model = tmp_path / "voice.onnx"
    model.write_bytes(b"mocked model, never executed")
    Path(str(model) + ".json").write_text(
        json.dumps({"phoneme_type": "espeak", "espeak": {"voice": "en-us"}})
    )
    loads = []

    class Voice:
        config = SimpleNamespace(sample_rate=8000)

        @staticmethod
        def load(path, *, config_path, use_cuda):
            loads.append((path, config_path, use_cuda))
            return Voice()

        def synthesize_wav(self, message, wav):
            wav.setnchannels(1)
            wav.setsampwidth(2)
            wav.setframerate(8000)
            wav.writeframes(b"\x00\x10" * 800)

    monkeypatch.setitem(sys.modules, "piper", SimpleNamespace(PiperVoice=Voice))
    piper = PiperTTS(model)
    assert piper.synthesize("One.").sample_rate == 8000
    assert piper.synthesize("Two.").channels == 1
    assert len(loads) == 1 and loads[0][2] is False
    piper.close()


def test_piper_preserves_native_synthesis_failure_instead_of_wave_header_error(
    tmp_path,
):
    class BlockedVoice:
        config = SimpleNamespace(sample_rate=22050)

        def synthesize_wav(self, message, wav):
            raise ImportError("Application Control blocked espeakbridge")

    piper = PiperTTS(None)
    piper.voice = BlockedVoice()
    with pytest.raises(ImportError, match="Application Control blocked"):
        piper.synthesize("Test.")


def test_piper_missing_assets_and_nonlocal_frontend_fail_without_download(tmp_path):
    with pytest.raises(VoiceUnavailable):
        PiperTTS(None).load()
    model = tmp_path / "voice.onnx"
    model.touch()
    with pytest.raises(VoiceUnavailable):
        PiperTTS(model).load()
    Path(str(model) + ".json").write_text('{"phoneme_type":"pinyin"}')
    with pytest.raises(VoiceUnavailable):
        PiperTTS(model).load()


def test_audio_start_uses_non_silent_pcm_and_device_timestamp(monkeypatch):
    class Stop(Exception):
        pass

    class RawStream:
        def __init__(self, **kwargs):
            self.kwargs = kwargs

        def __enter__(self):
            try:
                self.kwargs["callback"](
                    bytearray(2048),
                    1024,
                    SimpleNamespace(outputBufferDacTime=10.04, currentTime=10.0),
                    SimpleNamespace(output_underflow=False),
                )
            except Stop:
                self.kwargs["finished_callback"]()
            return self

        def __exit__(self, *args):
            return False

    monkeypatch.setitem(
        sys.modules,
        "sounddevice",
        SimpleNamespace(
            RawOutputStream=RawStream, CallbackStop=Stop, CallbackAbort=Stop
        ),
    )
    clip = AudioClip(b"\0\0" * 512 + b"\x00\x10" * 128, 8000)
    started = []
    SoundDevicePlayback(clock=lambda: 10.0).play(
        clip, lambda time, method: started.append((time, method)), Event()
    )
    assert started[0][0] == pytest.approx(10.104)
    assert "dac_estimate" in started[0][1]
    with pytest.raises(ValueError):
        SoundDevicePlayback().play(
            AudioClip(b"\0\0" * 128, 8000), lambda *args: None, Event()
        )


def test_event_log_is_bounded_and_persists_jsonl(tmp_path):
    path = tmp_path / "events.jsonl"
    log = EventLog(path)
    for i in range(1000):
        log.emit({"event": "test", "id": i})
    assert len(log.records) == 128
    log.close()
    assert len(path.read_text().splitlines()) == 1000


def test_fast_violation_queues_audio_while_semantic_request_is_still_blocked(backend):
    entered, release = Event(), Event()

    class SlowVerifier:
        def verify(self, frames, event_id, reason):
            entered.set()
            assert release.wait(3)
            newest = frames[-1]
            return SemanticResult(
                "UNCERTAIN",
                None,
                SemanticStatus.READY,
                newest.timestamp_s,
                newest.frame_id,
                event_id,
            )

    assistant = ProcedureAssistant(
        load_procedure(SAMPLE),
        default_actions(),
        fast_config=FastConfig(home_regions={"red_box": HomeRegion(0, 0, 0.4, 1)}),
        voice_config=VoiceConfig(speak_next_step=False),
        tts=FakeTTS(),
        player=FakePlayer(),
    )
    rows = [
        [Detection(2, "red_box", 0.9, BoundingBox(x - 5, 45, x + 5, 55), 1, True)]
        for x in (20, 60, 60, 60, 20, 20, 20)
    ]
    pipe = DetectorPipeline(
        DetectorConfig(backend="mock"),
        backend(rows),
        semantic_config=SemanticConfig(sample_every_frames=1, cooldown_s=0.01),
        verifier=SlowVerifier(),
    )
    try:
        wait_ready(assistant.alerts)
        image = np.zeros((100, 100, 3), np.uint8)
        for i in range(7):
            frame = adapt_image(image, i, i / 30)
            result = pipe.process(frame)
            assistant.observe(result, pipe.semantic_result)
        assert entered.wait(3) and not release.is_set()
        assert (
            assistant.state.status == "SKIPPED_STEP"
            and assistant.state.current_step_index == 1
        )
        wait_idle(assistant.alerts)
        assert any(
            r["event"] == "audio_playback_started" and r["alert_type"] == "SKIPPED_STEP"
            for r in assistant.log.records
        )
        assert pipe.semantic_result is None
    finally:
        release.set()
        pipe.close()
        assistant.close()


@pytest.mark.parametrize("scenario", ["correct", "skip", "wrong_order"])
def test_repaired_actual_fast_rules_voice_policy_and_no_double_error(scenario):
    from yolo.tests.test_procedure_repair import calibration, frame

    if scenario == "correct":
        positions = (
            [(0.1, 0.9)]
            + [(0.3, 0.9)] * 3
            + [(x, 0.9) for x in (0.46, 0.5, 0.54, 0.57, 0.59)]
            + [(0.1, 0.9)] * 3
            + [(0.1, 0.7)] * 3
            + [(0.1, x) for x in (0.6, 0.56, 0.52, 0.48, 0.45)]
            + [(0.1, 0.9)] * 3
        )
    elif scenario == "skip":
        positions = [
            (x, 0.9) for x in [0.1] + [0.3] * 3 + [0.7, 0.72, 0.74, 0.73] + [0.1] * 10
        ]
    else:
        # One wrong pick followed by carrying/manipulation on the same object;
        # incidental action must not become a second UNEXPECTED_ACTION warning.
        positions = [
            (0.1, y) for y in [0.9] + [0.7] * 10 + [0.6, 0.56, 0.52, 0.48, 0.45]
        ]
    player = FakePlayer()
    app = ProcedureAssistant(
        load_procedure(SAMPLE),
        default_actions(),
        fast_config=calibration(),
        voice_config=VoiceConfig(speak_next_step=False),
        tts=FakeTTS(),
        player=player,
    )
    try:
        wait_ready(app.alerts)
        for i, (red, yellow) in enumerate(positions):
            app.observe(
                frame(i, red, yellow)
            )  # actual classifier; injected tracks; no Qwen
        wait_idle(app.alerts)
        records = list(app.log.records)
        errors = [
            r
            for r in records
            if r["event"] in {"SKIPPED_STEP", "WRONG_ORDER", "UNEXPECTED_ACTION"}
        ]
        starts = [r for r in records if r["event"] == "audio_playback_started"]
        if scenario == "correct":
            assert app.state.status == "COMPLETED" and not errors and not starts
        else:
            assert len(errors) == len(starts) == len(player.clips) == 1
            assert errors[0]["event"] == (
                "SKIPPED_STEP" if scenario == "skip" else "WRONG_ORDER"
            )
            assert app.state.current_step_index == (1 if scenario == "skip" else 0)
    finally:
        app.close()
