"""Regression evidence for the approved architecture's pre-freeze repairs."""

from dataclasses import replace
from threading import Event

import pytest
from yolo.adapters.standalone import adapt_image
from yolo.core import config as core_config
from yolo.core.contracts import BoundingBox, Detection, DetectorConfig
from yolo.core.pipeline import DetectorPipeline
from yolo.pipeline import YoloPipeline
from yolo.semantic.contracts import SemanticConfig, SemanticResult, SemanticStatus

from shared.config import ConfigurationError
from shared.config import DetectorConfig as SIHDetectorConfig
from yolo import config as sih_config


def wait_done(worker):
    with worker._condition:
        assert worker._condition.wait_for(lambda: not worker._busy, timeout=3)


class RecordingVerifier:
    def __init__(self):
        self.calls = []

    def verify(self, frames, event_id, reason):
        newest = frames[-1]
        self.calls.append(newest.frame_id)
        return SemanticResult(
            "PICK_RED",
            "red_box",
            SemanticStatus.READY,
            newest.timestamp_s,
            newest.frame_id,
            event_id,
        )


@pytest.mark.parametrize("explicit_initialize", [True, False])
def test_semantic_pipeline_close_reuse_processes_new_event(
    backend, prepared, explicit_initialize
):
    verifier = RecordingVerifier()
    rows = [
        [Detection(2, "red_box", 0.9, BoundingBox(x, 50, x + 20, 80), 3)]
        for x in (20, 100, 20, 100)
    ]
    pipe = DetectorPipeline(
        DetectorConfig(backend="mock"),
        backend(rows),
        semantic_config=SemanticConfig(
            enabled=True, sample_every_frames=1, cooldown_s=0.1
        ),
        verifier=verifier,
    )
    data = prepared(max_width=None).image
    try:
        pipe.initialize()
        for i in range(2):
            pipe.process(adapt_image(data, i, float(i)))
        original = pipe.semantic
        wait_done(original)
        assert pipe.semantic_result.frame_id == 1 and original.status == "READY"
        pipe.close()
        assert original.closed and original.latest is None
        if explicit_initialize:
            pipe.initialize()
        for i in range(2, 4):
            pipe.process(adapt_image(data, i, float(i)))
        restarted = pipe.semantic
        assert restarted is not original and not restarted.closed
        assert restarted.verifier is verifier
        wait_done(restarted)
        assert verifier.calls == [1, 3]
        assert restarted.latest.frame_id == 3
        assert restarted.status == "READY"
        assert pipe.detector.initializations == 2
    finally:
        pipe.close()


def test_close_reuse_inflight_response_cannot_publish_or_overlap(backend, prepared):
    entered, release = Event(), Event()

    class SlowFirstVerifier(RecordingVerifier):
        def verify(self, frames, event_id, reason):
            if not self.calls:
                self.calls.append("inflight")
                entered.set()
                assert release.wait(3)
            return super().verify(frames, event_id, reason)

    verifier = SlowFirstVerifier()
    rows = [
        [Detection(2, "red_box", 0.9, BoundingBox(x, 50, x + 20, 80), 3)]
        for x in (20, 100, 20, 100)
    ]
    pipe = DetectorPipeline(
        DetectorConfig(backend="mock"),
        backend(rows),
        semantic_config=SemanticConfig(
            enabled=True, sample_every_frames=1, cooldown_s=0.1
        ),
        verifier=verifier,
    )
    data = prepared(max_width=None).image
    try:
        for i in range(2):
            pipe.process(adapt_image(data, i, float(i)))
        assert entered.wait(3)
        original = pipe.semantic
        pipe.close()
        pipe.initialize()
        for i in range(2, 4):
            pipe.process(adapt_image(data, i, float(i)))
        restarted = pipe.semantic
        assert restarted is not original
        assert restarted.verifier_lock is original.verifier_lock
        assert verifier.calls == [
            "inflight"
        ]  # new generation cannot concurrently use verifier
        assert restarted.status == "BUSY"
        assert not restarted.submit(restarted.buffer.select())
        release.set()
        wait_done(original)
        wait_done(restarted)
        assert original.latest is None
        assert verifier.calls == ["inflight", 1, 3]
        assert restarted.latest.frame_id == 3 and restarted.status == "READY"
    finally:
        release.set()
        pipe.close()


def test_config_facade_uses_canonical_helpers(monkeypatch, tmp_path):
    calls = []
    config = DetectorConfig(device="cpu")

    def load(path):
        calls.append(("load", path))
        return config

    def validate(value):
        assert isinstance(value, DetectorConfig)
        calls.append(("validate", value.device))
        return replace(value, device="cpu")

    def tracker(values, confidence_threshold):
        calls.append(("tracker", values, confidence_threshold))

    monkeypatch.setattr(core_config, "load_config", load)
    monkeypatch.setattr(core_config, "validate_config", validate)
    monkeypatch.setattr(core_config, "validate_tracker", tracker)
    assert isinstance(
        sih_config.load_config(tmp_path / "profile.yaml"), SIHDetectorConfig
    )
    assert sih_config.validate_config(SIHDetectorConfig(device="auto")).device == "cpu"
    sih_config.validate_tracker({"tracker_type": "bytetrack"}, 0.5)
    assert [c[0] for c in calls] == ["load", "validate", "tracker"]


def test_config_facade_preserves_shared_exception(tmp_path):
    with pytest.raises(ConfigurationError):
        sih_config.load_config(tmp_path / "missing.yaml")
    with pytest.raises(ConfigurationError):
        sih_config.validate_tracker({})


def test_sih_custom_backend_requires_shared_leaves(prepared, backend):
    private_leaf = Detection(2, "red_box", 0.9, BoundingBox(20, 30, 80, 90))
    with YoloPipeline(SIHDetectorConfig(), backend([[private_leaf]])) as pipe:
        output = pipe.process(prepared())
    assert output.status == "degraded" and output.detections == []
    assert any(
        d.code == "invalid_observation" and d.details["count"] == 1
        for d in output.warnings
    )
