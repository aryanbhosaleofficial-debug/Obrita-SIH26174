"""Optional output contracts, real local sockets/codec, controlled voice backend."""
import json
import socket
from time import monotonic, sleep
from urllib.request import urlopen

import cv2
import numpy as np

from integration.full_cli import build_runtime, main, options
from integration.outputs import LocalStream, VoiceOutput
from yolo.alerts.audio_cache import AudioClip
from yolo.alerts.contracts import VoiceConfig


def test_local_stream_jpeg_and_mjpeg_are_real_and_shutdown_releases_port():
    stream = LocalStream(port=0)
    port = stream.server.server_address[1]
    try:
        image = np.full((64, 80, 3), (0, 0, 255), np.uint8)
        stream.submit(image)
        with urlopen(f"http://127.0.0.1:{port}/frame.jpg", timeout=3) as response:
            jpeg = response.read()
        decoded = cv2.imdecode(np.frombuffer(jpeg, np.uint8), cv2.IMREAD_COLOR)
        assert decoded.shape == image.shape and decoded[32, 40, 2] > 200
        with urlopen(stream.url, timeout=3) as response:
            assert b"--frame" in response.read(128)
    finally:
        stream.close()
    assert not stream.thread.is_alive()
    stream.close()


def test_stream_port_in_use_degrades_without_stopping_fsm(tmp_path):
    with socket.socket() as occupied:
        occupied.bind(("127.0.0.1", 0))
        occupied.listen()
        assert main(["--synthetic", "--stream", "--stream-port", str(occupied.getsockname()[1]),
                     "--log", str(tmp_path / "events.jsonl")]) == 0
    summary = json.loads((tmp_path / "events.jsonl").read_text().splitlines()[-1])
    assert summary["procedure_state"] == "completed"
    assert summary["health"]["Streaming"] == "DEGRADED"


class FastTTS:
    def load(self):
        pass
    def synthesize(self, message):
        return AudioClip(np.full(2205, 1000, dtype=np.int16).tobytes(), 22050, 1, "test")
    def close(self):
        self.closed = True


class TestPlayback:
    __test__ = False
    def play(self, clip, on_start, cancel):
        on_start(monotonic(), "test_no_device")


def test_existing_alert_manager_worker_dispatches_and_closes_without_hardware(tmp_path):
    args = options(["--synthetic", "--scenario", "wrong-order", "--log", str(tmp_path / "events.jsonl")])
    system, frames, resources = build_runtime(args)
    records, tts = [], FastTTS()
    def emit(record):
        records.append(record)
        system.log.emit(record)
    voice = VoiceOutput(system.fsm.definition, VoiceConfig(), emit=emit, tts=tts, player=TestPlayback())
    deadline = monotonic() + 3
    while voice.status == "WARMING" and monotonic() < deadline:
        sleep(.01)
    assert voice.status == "READY"
    system.voice = voice
    system.consumer.alert_sink = system._alert
    system.realtime_fps = 200.
    with resources:
        result = system.run(frames)
    assert not result["error"]
    assert any(r["event"] == "alert_queued" for r in records)
    playback = [r for r in records if r["event"] == "audio_playback_started"]
    assert playback and system.latest_snapshot["spoken"] == playback[-1]["message"]
    assert not voice.manager._thread.is_alive() and tts.closed


def test_tts_failure_degrades_without_breaking_procedure(tmp_path):
    class BrokenTTS(FastTTS):
        def load(self):
            raise RuntimeError("voice unavailable")
    args = options(["--synthetic", "--log", str(tmp_path / "log.jsonl")])
    system, frames, resources = build_runtime(args)
    system.voice = VoiceOutput(system.fsm.definition, VoiceConfig(), emit=system.log.emit,
                               tts=BrokenTTS(), player=TestPlayback())
    system.consumer.alert_sink = system._alert
    with resources:
        summary = system.run(frames)
    assert summary["procedure_state"] == "completed" and not summary["error"]
    assert any(r.get("event") == "voice_unavailable" for r in system.log.records)
    assert summary["health"]["Voice"] == "DEGRADED"
    assert not system.latest_snapshot["spoken"]


def test_logger_constructor_failure_falls_back_to_memory(tmp_path):
    path = tmp_path / "cannot-be-directory"
    path.write_text("occupied")
    args = options(["--synthetic", "--log", str(path / "events.jsonl")])
    system, frames, resources = build_runtime(args)
    with resources:
        result = system.run(frames)
    assert result["procedure_state"] == "completed"
    assert result["health"]["Logging"] == "DEGRADED"
    assert system.log.records


def test_event_log_write_failure_is_exposed_as_degraded_health(tmp_path):
    args = options(["--synthetic", "--log", str(tmp_path / "events.jsonl")])
    system, frames, resources = build_runtime(args)
    class FailedDisk:
        def write(self, text):
            raise OSError("disk full")
    system.log.log._file = FailedDisk()
    with resources:
        result = system.run(frames)
    assert result["procedure_state"] == "completed" and not result["error"]
    assert system.log.error == "disk full"
    assert result["health"]["Logging"] == "DEGRADED"


def test_log_snapshot_is_detached_and_safe_during_voice_thread_writes():
    from threading import Thread
    from yolo.procedure.event_log import EventLog
    log = EventLog()
    log.emit({"event": "initial"})
    first = log.snapshot()
    first[0]["event"] = "caller edit"
    assert log.snapshot()[0]["event"] == "initial"
    worker = Thread(target=lambda: [log.emit({"event": "voice", "index": i}) for i in range(1000)])
    worker.start()
    for _ in range(100):
        assert len(log.snapshot()) <= 128
    worker.join(timeout=3)
    assert not worker.is_alive()
    assert log.snapshot()[-1]["index"] == 999
    log.close()


def test_stream_encoding_is_bounded_and_does_not_block_submit(monkeypatch):
    from threading import Event
    entered, release = Event(), Event()
    original = cv2.imencode
    def slow(*args):
        entered.set()
        assert release.wait(3)
        return original(*args)
    monkeypatch.setattr(cv2, "imencode", slow)
    stream = LocalStream(port=0)
    try:
        stream.submit(np.zeros((2, 2, 3), np.uint8))
        assert entered.wait(2)
        for i in range(100):
            stream.submit(np.full((2, 2, 3), i, np.uint8))
        assert stream.pending.shape == (2, 2, 3)
        assert stream.pending[0, 0, 0] == 99
    finally:
        release.set()
        stream.close()
    assert not stream.encoder.is_alive() and not stream.thread.is_alive()


def test_async_stream_encoding_failure_degrades_runtime(monkeypatch, tmp_path):
    monkeypatch.setattr(cv2, "imencode", lambda *args: (False, None))
    args = options(["--synthetic", "--stream", "--stream-port", "0", "--log", str(tmp_path / "events.jsonl")])
    system, frames, resources = build_runtime(args)
    system.realtime_fps = 200.
    with resources:
        summary = system.run(frames)
    assert summary["procedure_state"] == "completed" and not summary["error"]
    assert summary["health"]["Streaming"] == "DEGRADED"
    assert not system.latest_snapshot["lan_streaming"]
    assert any(r.get("output") == "Streaming" for r in system.log.records)


def test_real_recorder_failure_degrades_runtime(tmp_path):
    path = tmp_path / "occupied.avi"
    path.mkdir()
    args = options(["--synthetic", "--record", str(path), "--log", str(tmp_path / "events.jsonl")])
    system, frames, resources = build_runtime(args)
    system.realtime_fps = 200.
    with resources:
        summary = system.run(frames)
    assert summary["procedure_state"] == "completed" and not summary["error"]
    assert summary["health"]["Recording"] == "DEGRADED"
    assert not system.latest_snapshot["recording"]
    assert any(r.get("output") == "Recording" for r in system.log.records)
