"""Real Modules 03/04 evidence is consumed by Module 05 without schema changes."""
from copy import deepcopy
import pytest
from fusion.config import load_config
from fusion.pipeline import FusionPipeline
from integration.chain import PerceptionChain
from integration.milestone import MilestonePipeline
from integration.synthetic import scene, configure
from shared.config import PipelineConfig
from shared.schemas.activity_event import ActivityEvent
from shared.enums.module_status import ModuleStatus
from procedure.fsm import ProcedureFSM, StepOutcome


def pipeline():
    frames, detector, hands = scene()
    chain = PerceptionChain(configure(PipelineConfig()), detector=detector, hand_tracker=hands)
    return frames, MilestonePipeline(chain)


def test_packets_fused():
    frames, system = pipeline()
    with system:
        results = [system.process(frame) for frame in frames]
    events = [r.activity for r in results if r.activity.metadata["emitted"]]
    assert [e.activity_label for e in events] == ["touch_object", "move_object"]
    assert all(isinstance(e, ActivityEvent) for e in events)
    assert results[-1].activity.activity_label == "unknown"
    assert all(r.activity.frame_id == r.boundary.frame_id == r.upstream.optimization.frame_id == frame.frame_id
               for r, frame in zip(results, frames))
    assert all(r.activity.timestamp_s == frame.timestamp_s for r, frame in zip(results, frames))
    moving = next(e for e in events if e.activity_label == "move_object")
    assert moving.metadata["evidence"]["motion"]["value"] == "moving"
    result = results[moving.frame_id]
    spatial = result.upstream.optimization.spatial
    assert spatial.reference_frame.valid
    assert spatial.hands[0].reference_palm_center is not None
    d = result.upstream.optimization.object_frame.detections[0]
    assert d.reference_polygon and d.velocity_reference_frame is not None
    assert "motion" in moving.evidence_summary


def test_missing_boundary_packet():
    frames, system = pipeline()
    with system:
        upstream = [system.chain.process(frame) for frame in frames[:7]]
    with pytest.raises(ValueError, match="requires a boundary"):
        FusionPipeline().process(upstream[-1].optimization)
    cfg = load_config()
    cfg["input"]["allow_missing_boundary"] = True
    fusion = FusionPipeline(cfg)
    results = [fusion.process(r.optimization) for r in upstream]
    assert any(r.activity_label == "touch_object" and r.metadata["emitted"] for r in results)


def test_activity_event_consumed_by_fsm():
    frames, system = pipeline()
    fsm = ProcedureFSM(steps=[
        {"id": "touch", "expected_activity": "touch_object", "target_object": "sample_container"},
        {"id": "move", "expected_activity": "move_object", "target_object": "sample_container"},
    ])
    outcomes = []
    with system:
        for frame in frames:
            event = system.process(frame).activity
            if event.metadata["emitted"]:
                outcomes.append(fsm.on_event(event)[0])
    assert outcomes == [StepOutcome.CORRECT, StepOutcome.CORRECT]
    assert fsm.completed_steps == ["touch", "move"]


def test_offline_pipeline_and_models_initialize_once(monkeypatch):
    import socket
    def reject(*args, **kwargs):
        raise AssertionError("network is forbidden")
    monkeypatch.setattr(socket.socket, "connect", reject)
    monkeypatch.setattr(socket, "getaddrinfo", reject)
    monkeypatch.setattr(socket.socket, "sendto", reject)
    frames, system = pipeline()
    detector = system.chain.yolo.detector
    hands = system.chain.optimization.hand_tracker
    calls = {"detector": 0, "hands": 0}
    for name, backend in (("detector", detector), ("hands", hands)):
        original = backend.initialize
        def counted(name=name, original=original):
            calls[name] += 1
            original()
        monkeypatch.setattr(backend, "initialize", counted)
    originals = [f.image.copy() for f in frames]
    with system:
        results = [system.process(f) for f in frames]
        assert system.chain.yolo.semantic.config.enabled is False
    assert calls == {"detector": 1, "hands": 1}
    assert detector.closed and hands.closed
    import numpy as np
    assert all(np.array_equal(f.image, image) for f, image in zip(frames, originals))
    assert all(r.upstream.prepared.source.metadata == f.metadata for r, f in zip(results, frames))


def test_backend_failure_becomes_explicit_unknown(monkeypatch):
    frames, system = pipeline()
    def fail(image):
        raise RuntimeError("inference failure")
    monkeypatch.setattr(system.chain.yolo.detector, "detect", fail)
    with system:
        result = system.process(frames[0])
    assert result.upstream.objects.status == ModuleStatus.ERROR
    assert result.activity.activity_label == "unknown"
    assert not result.activity.metadata["emitted"]


def test_invalid_source_becomes_unknown():
    from dataclasses import replace
    frames, system = pipeline()
    with system:
        result = system.process(replace(frames[0], width=1))
    assert result.upstream.prepared.status == ModuleStatus.INVALID_INPUT
    assert result.activity.status == ModuleStatus.INVALID_INPUT
