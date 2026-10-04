"""Default-on semantics without synchronous inference or detector dependence."""

import json
from dataclasses import replace
from pathlib import Path
from threading import Event
from urllib.error import URLError

import cv2
import numpy as np
import pytest
from yolo.adapters.standalone import adapt_image
from yolo.core.contracts import BoundingBox, Detection, DetectorConfig
from yolo.core.pipeline import DetectorPipeline
from yolo.pipeline import YoloPipeline
from yolo.semantic.contracts import SemanticConfig, SemanticStatus
from yolo.semantic.qwen_verifier import QwenVerifier
from yolo.standalone_cli import load_semantic_config, main

from shared.config import DetectorConfig as SIHConfig
from shared.schemas.object_frame import ObjectFrame


def wait_status(worker, status):
    with worker._condition:
        assert worker._condition.wait_for(lambda: worker.status == status, timeout=3)


def wait_event(worker):
    with worker._condition:
        assert worker._condition.wait_for(lambda: not worker._busy, timeout=3)
    assert worker.latest is not None


def test_runtime_and_yaml_defaults_enable_semantics():
    assert load_semantic_config(None).enabled is True
    yaml_path = Path(__file__).resolve().parents[1] / "config/semantic.yaml"
    assert load_semantic_config(yaml_path) == SemanticConfig()


@pytest.mark.parametrize(
    "availability", ["READY", "MODEL_MISSING", "OLLAMA_UNAVAILABLE"]
)
def test_default_startup_checks_local_availability_without_inference(
    monkeypatch, backend, availability
):
    calls = []

    def request(self, endpoint, payload=None):
        calls.append(endpoint)
        assert endpoint == "/api/tags"
        if availability == "OLLAMA_UNAVAILABLE":
            raise URLError("local service stopped")
        return {
            "models": [{"name": self.config.model}] if availability == "READY" else []
        }

    monkeypatch.setattr(QwenVerifier, "_request", request)
    with DetectorPipeline(DetectorConfig(backend="mock"), backend()) as pipe:
        wait_status(pipe.semantic, availability)
        assert pipe.semantic.config.enabled and pipe.semantic._thread.is_alive()
        assert calls == ["/api/tags"] and pipe.semantic_result is None
        objects = pipe.process(adapt_image(np.zeros((120, 200, 3), np.uint8), 0, 0))
        assert objects.status == "no_detection"
        assert pipe.render(
            adapt_image(np.zeros((120, 200, 3), np.uint8), 0, 0), objects
        ).shape == (120, 200, 3)


@pytest.mark.parametrize("available", [True, False])
def test_default_sih_emits_objects_and_semantic_result_without_mutating_frames(
    monkeypatch, backend, prepared, detection, available
):
    calls = []

    def request(self, endpoint, payload=None):
        calls.append(endpoint)
        if not available:
            raise URLError("local service stopped")
        if endpoint == "/api/tags":
            return {"models": [{"name": self.config.model}]}
        assert endpoint == "/api/chat"
        return {"message": {"content": '{"action":"PICK_RED","object":"red_box"}'}}

    monkeypatch.setattr(QwenVerifier, "_request", request)
    rows = [
        [replace(detection, bbox=type(detection.bbox)(x, 30, x + 60, 90), track_id=3)]
        for x in (20, 100, 20, 100)
    ]
    with YoloPipeline(SIHConfig(), backend(rows)) as pipe:
        wait_status(pipe.semantic, "READY" if available else "OLLAMA_UNAVAILABLE")
        for i in range(4):
            frame = prepared(frame_id=i, timestamp=float(i))
            original, clean = frame.source.image.copy(), frame.image.copy()
            objects = pipe.process(frame)
            assert isinstance(objects, ObjectFrame) and objects.status == "ok"
            assert objects.detections[0].track_id == 3
            display = pipe.render(frame, objects)
            assert display.shape == original.shape
            assert np.array_equal(frame.source.image, original)
            assert np.array_equal(frame.image, clean)
        wait_event(pipe.semantic)
        assert pipe.semantic_result.status == (
            "READY" if available else "OLLAMA_UNAVAILABLE"
        )
        assert pipe.semantic_result.action == ("PICK_RED" if available else "UNCERTAIN")
        assert ("/api/chat" in calls) is available


@pytest.mark.parametrize(
    "flag,enabled", [(None, True), ("--no-vlm", False), ("--vlm", True)]
)
def test_cli_preserves_enable_disable_overrides(monkeypatch, tmp_path, flag, enabled):
    calls = []

    def request(self, endpoint, payload=None):
        calls.append(endpoint)
        return {"models": [{"name": self.config.model}]}

    monkeypatch.setattr(QwenVerifier, "_request", request)
    # Also exercise an explicit disabled YAML overridden by --vlm.
    semantic = tmp_path / "semantic.yaml"
    semantic.write_text("semantic: {enabled: false}")
    config = tmp_path / "detector.yaml"
    config.write_text("detector: {backend: none}")
    image, output = tmp_path / "input.png", tmp_path / "results.jsonl"
    assert cv2.imwrite(str(image), np.zeros((120, 200, 3), np.uint8))
    args = [
        "--source",
        str(image),
        "--config",
        str(config),
        "--no-display",
        "--jsonl",
        str(output),
    ]
    if flag:
        args.append(flag)
    if flag == "--vlm":
        args.extend(["--semantic-config", str(semantic)])
    assert main(args) == 0
    status = json.loads(output.read_text())["vlm_status"]
    assert (status != "DISABLED") is enabled
    if not enabled:
        assert calls == []
    assert not load_semantic_config(semantic).enabled


def test_default_trigger_is_not_per_frame_and_reset_remains_enabled(
    monkeypatch, backend
):
    chats = []

    def request(self, endpoint, payload=None):
        if endpoint == "/api/tags":
            return {"models": [{"name": self.config.model}]}
        chats.append(payload)
        return {"message": {"content": '{"action":"NONE","object":null}'}}

    monkeypatch.setattr(QwenVerifier, "_request", request)
    rows = [
        [Detection(2, "red_box", 0.9, BoundingBox(x, 30, x + 20, 60), 3)]
        for x in [20, 100] * 70
    ]
    with DetectorPipeline(DetectorConfig(backend="mock"), backend(rows)) as pipe:
        wait_status(pipe.semantic, "READY")
        image = np.zeros((120, 200, 3), np.uint8)
        for i in range(100):
            pipe.process(adapt_image(image, i, i / 10))
            with pipe.semantic._condition:
                assert pipe.semantic._condition.wait_for(
                    lambda: not pipe.semantic._busy, timeout=3
                )
        assert 0 < len(chats) <= 4
        assert pipe.detector.calls == 100
        assert len(pipe.semantic.buffer.frames) <= SemanticConfig().capacity
        assert all(len(chat["messages"][0]["images"]) <= 4 for chat in chats)
        pipe.reset()
        assert pipe.semantic.config.enabled and pipe.semantic._thread.is_alive()
        assert pipe.semantic.status == "WAITING" and pipe.semantic.latest is None
        assert not pipe.semantic.buffer.frames and pipe.semantic._pending is None
        for i in range(100, 140):
            pipe.process(adapt_image(image, i, i / 10))
        wait_event(pipe.semantic)
        assert pipe.semantic.latest.frame_id >= 100


@pytest.mark.parametrize("operation", ["reset", "close"])
def test_startup_probe_does_not_block_yolo_or_publish_stale_status(
    monkeypatch, backend, operation
):
    entered, release = Event(), Event()

    def check(self):
        entered.set()
        assert release.wait(3)
        return SemanticStatus.READY

    monkeypatch.setattr(QwenVerifier, "check_availability", check)
    pipe = DetectorPipeline(DetectorConfig(backend="mock"), backend())
    try:
        assert entered.wait(3)
        pipe.initialize()
        objects = pipe.process(adapt_image(np.zeros((120, 200, 3), np.uint8), 0, 0))
        assert objects.status == "no_detection" and not release.is_set()
        getattr(pipe, operation)()
        release.set()
        with pipe.semantic._condition:
            # Wait for the probe to leave the serialized verifier section.
            assert pipe.semantic.verifier_lock.acquire(timeout=3)
            pipe.semantic.verifier_lock.release()
        assert pipe.semantic.status == "WAITING"
        assert pipe.semantic.latest is None
    finally:
        release.set()
        pipe.close()


def test_default_qwen_worker_processes_events_after_close_reuse(monkeypatch, backend):
    chats = []

    def request(self, endpoint, payload=None):
        if endpoint == "/api/tags":
            return {"models": [{"name": self.config.model}]}
        chats.append(payload)
        return {"message": {"content": '{"action":"NONE","object":null}'}}

    monkeypatch.setattr(QwenVerifier, "_request", request)
    rows = [
        [Detection(2, "red_box", 0.9, BoundingBox(x, 30, x + 20, 60), 3)]
        for x in [20, 100] * 4
    ]
    pipe = DetectorPipeline(DetectorConfig(backend="mock"), backend(rows))
    image = np.zeros((120, 200, 3), np.uint8)
    try:
        for start in (0, 4):
            pipe.initialize()
            wait_status(pipe.semantic, "READY")
            for i in range(start, start + 4):
                pipe.process(adapt_image(image, i, float(i)))
            wait_event(pipe.semantic)
            assert pipe.semantic.latest.frame_id == start + 2
            assert pipe.semantic.status == "READY"
            if start == 0:
                old = pipe.semantic
                pipe.close()
                assert old.closed and old.latest is None
        assert pipe.semantic is not old
        assert pipe.semantic.verifier is old.verifier
        assert len(chats) == 2
    finally:
        pipe.close()
