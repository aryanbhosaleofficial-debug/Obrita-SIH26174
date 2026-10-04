"""Offline regression checks for adapters, rendering, semantics and isolation."""

import json
import shutil
import subprocess
import sys
from dataclasses import asdict, replace
from pathlib import Path
from threading import Event
from urllib.error import HTTPError, URLError

import cv2
import numpy as np
import pytest
from optimization.pipeline import OptimizationPipeline
from yolo.adapters.sih import adapt_prepared
from yolo.adapters.standalone import adapt_image
from yolo.core.contracts import (
    BoundingBox,
    Detection,
    DetectorConfig,
    InputFrame,
)
from yolo.core.contracts import (
    DetectionFrame as ObjectFrame,
)
from yolo.core.pipeline import DetectorPipeline
from yolo.inputs.opencv_source import InputSourceError, OpenCVSource
from yolo.pipeline import YoloPipeline
from yolo.semantic.contracts import SemanticConfig, SemanticResult, SemanticStatus
from yolo.semantic.event_trigger import EventTrigger
from yolo.semantic.qwen_verifier import QwenVerifier, parse_response
from yolo.semantic.temporal_buffer import TemporalBuffer
from yolo.semantic.worker import SemanticWorker
from yolo.standalone_cli import load_semantic_config, main
from yolo.visualization.renderer import FrameRenderer, VisualizationError

from shared.config import DetectorConfig as SIHConfig
from shared.config import HandTrackerConfig, PipelineConfig
from shared.schemas.object_frame import ObjectFrame as SIHObjectFrame


def image():
    return np.zeros((120, 200, 3), np.uint8)


def objects(i=0, timestamp=None, x=20, present=True):
    return ObjectFrame(
        i,
        float(i) if timestamp is None else timestamp,
        200,
        120,
        [Detection(2, "red_box", 0.9, BoundingBox(x, 50, x + 20, 80), 3)]
        if present
        else [],
    )


def wait_done(worker):
    with worker._condition:
        assert worker._condition.wait_for(lambda: not worker._busy, timeout=3)


def test_standalone_adapter_same_core(backend):
    data = image()
    frame = adapt_image(data, 4, 1.5)
    assert isinstance(frame, InputFrame) and frame.image is data
    with DetectorPipeline(
        DetectorConfig(backend="mock"), backend([objects().detections])
    ) as pipe:
        result = pipe.process(frame)
        assert result.detections[0].bbox_xyxy == (20, 50, 40, 80)
        assert result.frame_id == 4 and result.timestamp_s == 1.5


@pytest.mark.parametrize(
    "data",
    [
        np.zeros((0, 3, 3), np.uint8),
        np.zeros((4, 5), np.uint8),
        np.zeros((4, 5, 3), float),
    ],
)
def test_standalone_adapter_rejects_bad_input(data):
    with pytest.raises(ValueError):
        adapt_image(data)


def test_sih_adapter_preserves_metadata_scale_and_clean_image(prepared):
    original = prepared(width=803, height=401, color="RGB")
    adapted = adapt_prepared(original)
    assert adapted.image is original.image
    assert adapted.source.image is original.source.image
    assert adapted.scale_x == original.scale_x and adapted.scale_y == original.scale_y
    assert adapted.source.frame_id == original.source.frame_id
    assert adapted.source.session_id == original.source.session_id
    assert (
        adapted.warnings == original.warnings
        and adapted.warnings is not original.warnings
    )


def test_integrated_renderer_and_module03(prepared, backend, detection, monkeypatch):
    p = prepared(width=803, height=401, max_width=400, color="RGB")
    source_before, ai_before = p.source.image.copy(), p.image.copy()
    rectangles = []
    actual = cv2.rectangle

    def capture(data, p1, p2, *args):
        rectangles.append((p1, p2))
        return actual(data, p1, p2, *args)

    monkeypatch.setattr(cv2, "rectangle", capture)
    optimizer = OptimizationPipeline(
        PipelineConfig(hand_tracker=HandTrackerConfig(enabled=False, backend="none"))
    )
    try:
        with YoloPipeline(SIHConfig(), backend([[detection]])) as pipe:
            result = pipe.process(p)
            assert type(result) is SIHObjectFrame
            display = pipe.render(p, result)
            assert display.shape == p.source.image.shape
            assert rectangles == [
                (
                    (round(20 / p.scale_x), round(30 / p.scale_y)),
                    (round(80 / p.scale_x), round(90 / p.scale_y)),
                )
            ]
            assert not np.shares_memory(display, p.source.image)
            assert np.array_equal(source_before, p.source.image) and np.array_equal(
                ai_before, p.image
            )
            assert optimizer.process(p, result).object_frame.frame_id == result.frame_id
    finally:
        optimizer.close()


def test_renderer_empty_and_wrong_space():
    frame = adapt_image(image())
    output = FrameRenderer().render(frame.source, objects(present=False))
    assert output.shape == image().shape
    resized = replace(frame.source, image=np.zeros((60, 100, 3), np.uint8))
    with pytest.raises(VisualizationError, match="source-coordinate"):
        FrameRenderer().render(resized, objects())
    with pytest.raises(VisualizationError):
        FrameRenderer().render(replace(frame.source, frame_id=5), objects())


def test_renderer_stale_event_is_identified(monkeypatch):
    text = []
    actual = cv2.putText

    def capture(data, label, *args):
        text.append(label)
        return actual(data, label, *args)

    monkeypatch.setattr(cv2, "putText", capture)
    frame = adapt_image(image(), 20, 20.0)
    semantic = SemanticResult("PICK_RED", "red_box", SemanticStatus.READY, 3.0, 3, 2)
    FrameRenderer().render(
        frame.source, objects(20), semantic, vlm_status="READY", tracking=True
    )
    assert any("Frame:3 Time:3.000s" in s for s in text)
    assert any("Last semantic event:2 PICK_RED" in s for s in text)


def test_temporal_buffer_bounded_ordered_detached_reset():
    c = SemanticConfig(
        capacity=4, keyframes=3, sample_every_frames=1, max_image_side=64
    )
    buffer = TemporalBuffer(c)
    data = image()
    for i in range(10):
        buffer.append(data, objects(i))
    assert len(buffer.frames) == 4
    selected = buffer.select()
    assert [f.frame_id for f in selected] == [6, 7, 9]
    assert max(len(f.jpeg) for f in selected) <= 1024 * 1024
    encoded_before = selected[-1].jpeg
    data[:] = 255
    assert selected[-1].jpeg == encoded_before
    decoded = cv2.imdecode(np.frombuffer(encoded_before, np.uint8), cv2.IMREAD_COLOR)
    assert max(decoded.shape[:2]) == 64
    buffer.clear()
    assert not buffer.frames


def test_temporal_sampling():
    buffer = TemporalBuffer(SemanticConfig(sample_every_frames=2))
    for i in range(7):
        buffer.append(image(), objects(i))
    assert [f.frame_id for f in buffer.select()] == [0, 2, 4, 6]


@pytest.mark.parametrize("dx,dy", [(50, 0), (-50, 0), (0, 50), (0, -50)])
def test_event_trigger_has_no_gravity_direction(dx, dy):
    trigger = EventTrigger(SemanticConfig(cooldown_s=1, displacement_threshold=0.04))
    first = objects()
    assert trigger.check(first) is None
    moved = objects(1, x=20 + dx)
    moved.detections[0].bbox = BoundingBox(20 + dx, 50 + dy, 40 + dx, 80 + dy)
    assert trigger.check(moved) == "track_displacement"
    assert trigger.check(replace(moved, frame_id=2, timestamp_s=1.5)) is None
    trigger.clear()
    assert trigger.check(moved) is None


def test_appearance_and_manual_interval_trigger():
    trigger = EventTrigger(SemanticConfig(cooldown_s=1, interval_s=5))
    assert trigger.check(objects()) is None
    assert trigger.check(objects(1, present=False)) == "object_appearance_change"
    assert trigger.check(objects(3, present=False)) is None
    assert trigger.check(objects(6, present=False)) == "manual_interval"


@pytest.mark.parametrize(
    "text,action,status",
    [
        ('{"action":"PICK_RED","object":"red_box"}', "PICK_RED", "READY"),
        ('{"action":"NONE","object":null}', "NONE", "READY"),
        ('{"action":"UNCERTAIN","object":null}', "UNCERTAIN", "READY"),
        ('{"action":"RUN","object":"red_box"}', "UNCERTAIN", "VLM_PARSE_ERROR"),
        ('{"action":"PICK_RED","object":"yellow_box"}', "UNCERTAIN", "VLM_PARSE_ERROR"),
        (
            '{"action":"PICK_RED","object":"red_box","confidence":0.87}',
            "UNCERTAIN",
            "VLM_PARSE_ERROR",
        ),
        (
            '{"action":"PICK_RED","action":"NONE","object":null}',
            "UNCERTAIN",
            "VLM_PARSE_ERROR",
        ),
        (
            '```json\n{"action":"NONE","object":null}\n```',
            "UNCERTAIN",
            "VLM_PARSE_ERROR",
        ),
        ('{"action":3,"object":null}', "UNCERTAIN", "VLM_PARSE_ERROR"),
        ("[]", "UNCERTAIN", "VLM_PARSE_ERROR"),
        ("nonsense", "UNCERTAIN", "VLM_PARSE_ERROR"),
    ],
)
def test_qwen_parser(text, action, status):
    result = parse_response(text, SemanticConfig(), frame_id=9, timestamp_s=4.0)
    assert result.action == action and result.status == status
    assert result.frame_id == 9 and result.timestamp_s == 4.0
    assert "confidence" not in asdict(result)


@pytest.mark.parametrize(
    "host",
    [
        "https://localhost:11434",
        "http://example.com",
        "http://192.168.1.1:11434",
        "http://localhost:11434/path",
        "http://user@localhost:11434",
        "http://localhost:11434?q=x",
    ],
)
def test_no_remote_hosts(host):
    with pytest.raises(ValueError):
        SemanticConfig(host=host)


@pytest.mark.parametrize(
    "values",
    [
        {"capacity": 1000},
        {"keyframes": 1},
        {"sample_every_frames": 0},
        {"timeout_s": float("nan")},
        {"enabled": "true"},
        {"model": "qwen-cloud"},
    ],
)
def test_semantic_config_validation(values):
    with pytest.raises(ValueError):
        SemanticConfig(**values)


def test_qwen_payload_schema_context_and_chronology(monkeypatch):
    verifier = QwenVerifier(SemanticConfig(enabled=True, sample_every_frames=1))
    requests = []

    def request(endpoint, payload=None):
        requests.append((endpoint, payload))
        return (
            {"models": [{"name": verifier.config.model}]}
            if endpoint == "/api/tags"
            else {"message": {"content": '{"action":"PICK_RED","object":"red_box"}'}}
        )

    monkeypatch.setattr(verifier, "_request", request)
    buffer = TemporalBuffer(verifier.config)
    for i in range(4):
        buffer.append(image(), objects(i))
    result = verifier.verify(buffer.select(), 7, "track_displacement")
    payload = requests[-1][1]
    assert result.status == "READY" and result.frame_id == 3 and result.event_id == 7
    assert payload["model"] == "qwen3-vl:2b-instruct" and payload["stream"] is False
    assert len(payload["messages"][0]["images"]) == 4
    assert "chronological" in payload["messages"][0]["content"]
    assert "source_bbox_xyxy" in payload["messages"][0]["content"]
    assert payload["format"]["additionalProperties"] is False


@pytest.mark.parametrize(
    "response,status",
    [
        ({"models": []}, "MODEL_MISSING"),
        (
            {"models": [{"name": "qwen3-vl:2b-instruct", "remote_host": "cloud"}]},
            "MODEL_MISSING",
        ),
        (URLError("down"), "OLLAMA_UNAVAILABLE"),
        (TimeoutError(), "OLLAMA_UNAVAILABLE"),
        ({}, "VLM_ERROR"),
    ],
)
def test_ollama_availability(response, status, monkeypatch):
    verifier = QwenVerifier(SemanticConfig(enabled=True))

    def request(*args):
        if isinstance(response, Exception):
            raise response
        return response

    monkeypatch.setattr(verifier, "_request", request)
    assert verifier.check_availability() == status


def test_vlm_failure_preserves_yolo_and_renderer(backend, monkeypatch):
    config = SemanticConfig(enabled=True, cooldown_s=0.1, sample_every_frames=1)
    verifier = QwenVerifier(config)
    monkeypatch.setattr(
        verifier, "_request", lambda *a: (_ for _ in ()).throw(URLError("stopped"))
    )
    with DetectorPipeline(
        DetectorConfig(backend="mock"),
        backend([objects().detections, objects(x=80).detections]),
        semantic_config=config,
        verifier=verifier,
    ) as pipe:
        assert pipe.process(adapt_image(image(), 0, 0)).status == "ok"
        frame = adapt_image(image(), 1, 1)
        result = pipe.process(frame)
        wait_done(pipe.semantic)
        assert result.status == "ok" and result.detections[0].track_id == 3
        assert pipe.semantic_result.status == "OLLAMA_UNAVAILABLE"
        assert pipe.render(frame, result).shape == image().shape


def test_worker_bounded_nonblocking_and_reset_discards_late_reply():
    entered, release = Event(), Event()

    class SlowVerifier:
        def verify(self, frames, event_id, reason):
            entered.set()
            assert release.wait(3)
            return SemanticResult(
                "PICK_RED", "red_box", SemanticStatus.READY, 0, 0, event_id
            )

    worker = SemanticWorker(SemanticConfig(enabled=True), SlowVerifier())
    buffer = TemporalBuffer(worker.config)
    buffer.append(image(), objects())
    try:
        assert worker.submit(buffer.select())
        assert entered.wait(3)
        assert not worker.submit(buffer.select())
        worker.reset()
        assert worker.latest is None and not worker.buffer.frames
        assert not worker.submit(buffer.select())  # old generation still in flight
        release.set()
        wait_done(worker)
        assert worker.latest is None and worker.status == "WAITING"
    finally:
        release.set()
        worker.close()


def test_pipeline_upstream_reset_clears_semantics_not_weights(
    prepared, backend, detection
):
    class Tracker(backend):
        resets = 0

        def reset_tracking(self):
            self.resets += 1

    fake = Tracker([[detection]])
    with YoloPipeline(
        SIHConfig(), fake, semantic_config=SemanticConfig(enabled=True)
    ) as pipe:
        first = prepared(frame_id=1, timestamp=1)
        pipe.process(first)
        pipe.semantic._latest = SemanticResult(
            "PICK_RED", "red_box", SemanticStatus.READY, 1, 1
        )
        pipe.process(replace(prepared(frame_id=2, timestamp=2), reset_required=True))
        assert pipe.semantic_result is None
        assert len(pipe.semantic.buffer.frames) == 1
        assert fake.initializations == 1 and fake.resets == 1


def test_disabled_semantics_never_contacts_ollama(backend):
    with DetectorPipeline(DetectorConfig(backend="mock"), backend()) as pipe:
        for i in range(10):
            pipe.process(adapt_image(image(), i, float(i)))
        assert pipe.semantic.status == "DISABLED" and pipe.semantic._thread is None
        assert not pipe.semantic.buffer.frames


def test_standalone_image_and_video_outputs(tmp_path, capsys):
    config = tmp_path / "none.yaml"
    config.write_text("detector: {backend: none}")
    photo = tmp_path / "input.png"
    assert cv2.imwrite(str(photo), image())
    annotated, logs = tmp_path / "annotated.png", tmp_path / "objects.jsonl"
    assert (
        main(
            [
                "--source",
                str(photo),
                "--config",
                str(config),
                "--no-display",
                "--output",
                str(annotated),
                "--jsonl",
                str(logs),
            ]
        )
        == 0
    )
    assert cv2.imread(str(annotated)).shape == image().shape
    assert json.loads(logs.read_text())["vlm_status"] == "DISABLED"
    video, out = tmp_path / "input.mp4", tmp_path / "annotated.mp4"
    writer = cv2.VideoWriter(
        str(video), cv2.VideoWriter_fourcc(*"mp4v"), 10, (200, 120)
    )
    assert writer.isOpened()
    for _ in range(3):
        writer.write(image())
    writer.release()
    assert (
        main(
            [
                "--source",
                str(video),
                "--config",
                str(config),
                "--no-display",
                "--output",
                str(out),
            ]
        )
        == 0
    )
    with OpenCVSource(out) as source:
        assert len(list(source)) == 3


def test_webcam_structure_and_cleanup(monkeypatch):
    class Camera:
        released = False

        def __init__(self, source):
            assert source == 0

        def isOpened(self):
            return True

        def get(self, key):
            return 30

        def read(self):
            return True, image()

        def release(self):
            self.released = True

    camera = Camera(0)
    monkeypatch.setattr(cv2, "VideoCapture", lambda source: camera)
    with OpenCVSource("0") as source:
        assert next(iter(source))[0] == 0
    assert camera.released


def test_standalone_input_errors(tmp_path):
    with pytest.raises(InputSourceError):
        OpenCVSource(tmp_path / "missing.mp4")
    bad = tmp_path / "bad.jpg"
    bad.write_bytes(b"bad")
    with pytest.raises(InputSourceError):
        OpenCVSource(bad)
    assert main(["--source", str(bad), "--no-display"]) == 2


def test_copy_outside_repo_isolation(tmp_path):
    owner = Path(__file__).resolve().parents[1]
    copied = tmp_path / "orbita_module02"
    shutil.copytree(
        owner,
        copied,
        ignore=shutil.ignore_patterns(
            ".verification", "__pycache__", "tests", "*.pt", "HAR.zip"
        ),
    )
    assert cv2.imwrite(str(copied / "input.png"), image())
    (copied / "none.yaml").write_text("detector: {backend: none}")
    script = """
import importlib.abc,sys,socket
class Guard(importlib.abc.MetaPathFinder):
 def find_spec(self,fullname,*args):
  if fullname.split('.')[0] in {'shared','perception','optimization','integration','procedure','FSM','GUI','alerts'}:
   raise AssertionError('forbidden standalone import: '+fullname)
sys.meta_path.insert(0,Guard())
def reject(*args,**kwargs): raise AssertionError('network attempted')
socket.socket.connect=reject
socket.socket.sendto=reject
socket.getaddrinfo=reject
import standalone
standalone.bootstrap()
from yolo.standalone_cli import main
assert main(['--source','input.png','--config','none.yaml','--no-display','--output','out.png'])==0
"""
    result = subprocess.run(
        [sys.executable, "-c", script],
        cwd=copied,
        capture_output=True,
        text=True,
        timeout=20,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert (copied / "out.png").is_file()


def test_semantic_yaml_config(tmp_path):
    path = tmp_path / "semantic.yaml"
    path.write_text("semantic: {enabled: true, interval_s: 10}")
    assert load_semantic_config(path).enabled
    path.write_text("semantic: {unknown: 42}")
    with pytest.raises(ValueError):
        load_semantic_config(path)


@pytest.mark.parametrize(
    "failure,status",
    [
        (HTTPError("local", 404, "missing", {}, None), "MODEL_MISSING"),
        (HTTPError("local", 500, "error", {}, None), "VLM_ERROR"),
        (TimeoutError(), "OLLAMA_UNAVAILABLE"),
        ({"message": {"content": "invalid"}}, "VLM_PARSE_ERROR"),
    ],
)
def test_qwen_inference_failure_is_structured(failure, status, monkeypatch):
    config = SemanticConfig(enabled=True, sample_every_frames=1)
    verifier = QwenVerifier(config)

    def request(endpoint, payload=None):
        if endpoint == "/api/tags":
            return {"models": [{"name": config.model}]}
        if isinstance(failure, Exception):
            raise failure
        return failure

    monkeypatch.setattr(verifier, "_request", request)
    buffer = TemporalBuffer(config)
    for i in range(2):
        buffer.append(image(), objects(i))
    result = verifier.verify(buffer.select(), 10, "manual_interval")
    assert result.action == "UNCERTAIN" and result.status == status
    assert result.frame_id == 1 and result.event_id == 10


def test_standalone_pipeline_rejects_wrong_contract(backend):
    with (
        DetectorPipeline(DetectorConfig(backend="mock"), backend()) as pipeline,
        pytest.raises(TypeError, match="InputFrame"),
    ):
        pipeline.process(image())


def test_invalid_reset_frame_clears_semantics(prepared, backend):
    with YoloPipeline(
        SIHConfig(), backend(), semantic_config=SemanticConfig(enabled=True)
    ) as pipe:
        pipe.semantic._latest = SemanticResult(
            "PICK_RED", "red_box", SemanticStatus.READY, 1, 1
        )
        frame = replace(prepared(), reset_required=True, accepted=False)
        assert pipe.process(frame).status == "invalid_input"
        assert pipe.semantic_result is None and not pipe.semantic.buffer.frames
