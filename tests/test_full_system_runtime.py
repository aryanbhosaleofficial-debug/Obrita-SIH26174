"""Full logical system, all real owner stages, inference-only and semantic fixtures."""
from dataclasses import replace
import json
from pathlib import Path
from queue import Queue
import socket
import threading

import cv2
import numpy as np
import pytest

from integration.full_cli import build_runtime, main, options, ROOT
from integration.full_system import require_frame_identity
from integration.activity import ActivityAdapter
from pose_tracking.sync import FrameSyncError
from procedure.contracts import DecisionType as D


def runtime(tmp_path, scenario="correct", **kwargs):
    args = options(["--synthetic", "--scenario", scenario, "--log", str(tmp_path / "events.jsonl")])
    return build_runtime(args, **kwargs)


@pytest.mark.parametrize("scenario,state,decisions", [
    ("correct", "completed", ["valid"] * 4),
    ("wrong-order", "recovery_required", ["wrong_order"]),
    ("skip", "recovery_required", ["valid", "skipped_step"]),
    ("recovery", "completed", ["valid", "skipped_step", "valid", "valid", "valid"]),
    ("repeated", "in_progress", ["valid", "repeated_action"]),
])
def test_scenarios_run_all_modules_and_log_guidance(tmp_path, scenario, state, decisions):
    system, frames, resources = runtime(tmp_path, scenario)
    with resources:
        summary = system.run(frames)
    assert summary["error"] is None
    assert summary["frames"] == 72 and summary["procedure_state"] == state
    records = [json.loads(line) for line in system.log.path.read_text().splitlines()]
    activities = [r for r in records if r["event"] == "activity_confirmed"]
    observed = [r["decision"] for r in records if r["event"] == "guidance" and r["decision"] != "state_changed"]
    # Ignored repetition intentionally creates no guidance log; activity remains audited.
    assert observed == [d for d in decisions if d != "repeated_action"]
    assert len(activities) == len(decisions)
    assert all(r["metadata"]["synthetic"] for r in activities)
    assert all(r["utc"] and r["session_id"] for r in records)
    assert system.closed and system.pipeline.chain._closed
    if scenario == "recovery":
        assert [r["event"] for r in records if r["event"].startswith("recovery_")] == ["recovery_entered", "recovery_completed"]


def test_real_fusion_rules_reach_fsm_with_no_semantic_simulator(tmp_path):
    args = options(["--synthetic", "--scenario", "fusion", "--procedure", str(ROOT / "procedures/fusion_touch_move.yaml"),
                    "--log", str(tmp_path / "events.jsonl")])
    system, frames, resources = build_runtime(args)
    assert system.scenario is None
    with resources:
        summary = system.run(frames)
    assert summary["completed_steps"] == ["touch", "move"]
    activities = [r for r in system.log.records if r.get("event") == "activity_confirmed"]
    assert [r["activity_label"] for r in activities] == ["touch_object", "move_object"]


def test_duplicate_deliveries_do_not_double_progress_and_warning_dedupes(tmp_path):
    system, frames, resources = runtime(tmp_path, "wrong-order")
    original = system.scenario.event
    calls = []
    class Voice:
        enabled = True
        status = "TEST"
        def enqueue(self, value):
            calls.append(value)
            return True
        def close(self):
            pass
    system.voice = Voice()
    system.consumer.alert_sink = system._alert
    def replay(packet):
        event = original(packet)
        if event:
            replay.last = event
        # Duplicate packets cannot be relabeled to bypass temporal checks; replay
        # exact identity directly at dispatcher boundary, not new physical frames.
        if getattr(replay, "last", None):
            assert system.consumer.process(replay.last).decision in (D.WRONG_ORDER, D.DUPLICATE)
        return event
    system.scenario.event = replay
    with resources:
        summary = system.run(frames)
    assert summary["completed_steps"] == []
    assert len([c for c in calls if c.alert_type == "WRONG_ORDER"]) == 1
    assert system.fsm.current_index == 0


@pytest.mark.parametrize("field", ["frame_id", "timestamp_s", "source_id", "session_id"])
def test_identity_mismatch_stops_before_fsm(tmp_path, field):
    system, frames, resources = runtime(tmp_path)
    original = system.pipeline.process
    def mismatch(packet):
        result = original(packet)
        if field in ("frame_id", "timestamp_s"):
            setattr(result.activity, field, 999)
        else:
            result.activity.metadata[field] = "foreign"
        return result
    system.pipeline.process = mismatch
    with resources:
        summary = system.run(frames)
    assert "FrameSyncError" in summary["error"]
    assert not summary["completed_steps"]
    assert summary["frames"] == 0


def test_gui_payload_uses_real_adapter_and_bgr_frames(tmp_path):
    pytest.importorskip("PySide6")
    from GUI.orbita_gui.adapters import snapshot_from_dict
    class GUI:
        def __init__(self):
            self.snapshots, self.frames = [], []
        def push_snapshot(self, value):
            self.snapshots.append(snapshot_from_dict(value))
        def push_frame(self, value):
            self.frames.append(value)
    gui = GUI()
    system, frames, resources = runtime(tmp_path, gui=gui)
    with resources:
        summary = system.run(frames)
    assert summary["error"] is None and gui.frames
    assert gui.snapshots[-1].next_step.head == "Completed"
    assert gui.snapshots[-1].log and gui.snapshots[-1].chain
    assert all(f.dtype == np.uint8 and f.shape == (240, 320, 3) for f in gui.frames)
    assert not gui.snapshots[-1].scene.simulated
    assert gui.snapshots[-1].scene.overlays_rendered


@pytest.mark.parametrize("rotation", [0, 90, 180])
def test_orientation_preserves_physical_rack_coordinates_and_fsm(tmp_path, rotation):
    args = options(["--synthetic", "--rotation", str(rotation), "--log", str(tmp_path / "log.jsonl")])
    system, frames, resources = build_runtime(args)
    seen = []
    def inspect(row):
        if row["frame_id"] == 0:
            seen.append(row["tracking"])
    system.diagnostics = inspect
    with resources:
        summary = system.run(frames)
    assert summary["procedure_state"] == "completed" and summary["error"] is None
    tracking = seen[0]
    assert tracking["feature_coordinate_frame"] == "rack_relative"
    assert tracking["body_landmarks"][0]["rack_xy"] == pytest.approx((.35, .3), abs=1e-5)
    assert [h["handedness"] for h in tracking["hands"]] == ["LEFT", "RIGHT"]


def test_recorded_video_is_decodable_and_metadata_is_synchronized(tmp_path):
    path = tmp_path / "recording with spaces.avi"
    assert main(["--synthetic", "--record", str(path), "--log", str(tmp_path / "log.jsonl")]) == 0
    cap = cv2.VideoCapture(str(path))
    try:
        assert cap.isOpened()
        count = 0
        while True:
            ok, image = cap.read()
            if not ok:
                break
            assert image.shape == (240, 320, 3)
            count += 1
    finally:
        cap.release()
    metadata = [json.loads(line) for line in path.with_suffix(".avi.jsonl").read_text().splitlines()]
    assert count == len(metadata) and count > 0
    assert len({r["frame_id"] for r in metadata}) == count
    assert all(r["timestamp_s"] == r["frame_id"] / 30 for r in metadata)


def test_interrupt_and_source_error_release_all_resources(tmp_path):
    system, frames, resources = runtime(tmp_path)
    released = []
    def interrupted():
        try:
            yield next(frames)
            raise KeyboardInterrupt
        finally:
            released.append(True)
    with resources:
        summary = system.run(interrupted())
    assert summary["exit_reason"] == "interrupt" and not summary["error"]
    assert released and system.closed and system.pipeline.chain._closed


def test_gui_close_stop_request_finishes_and_releases(tmp_path):
    stop = threading.Event()
    system, frames, resources = runtime(tmp_path, stop=stop)
    def sequence():
        yield next(frames)
        stop.set()
        yield next(frames)
    with resources:
        summary = system.run(sequence())
    assert summary["exit_reason"] == "stop_requested" and summary["frames"] == 1


def test_optional_output_failure_does_not_break_procedure(tmp_path):
    class BrokenGUI:
        def push_frame(self, value):
            raise OSError("window unavailable")
        def push_snapshot(self, value):
            raise OSError("window unavailable")
    system, frames, resources = runtime(tmp_path, gui=BrokenGUI())
    with resources:
        summary = system.run(frames)
    assert summary["procedure_state"] == "completed" and summary["error"] is None
    assert summary["health"]["GUI"] == "DEGRADED"


def test_semantic_adapter_preserves_evidence_and_explicit_proxy_metadata(tmp_path):
    system, frames, resources = runtime(tmp_path)
    event = system.scenario.event(list(frames)[11])
    event.activity_label = "touch_object"
    event.metadata["synthetic"] = False
    mapper = ActivityAdapter.from_yaml(ROOT / "configs/red_yellow_demo_proxy.yaml")
    mapped = mapper.adapt(event)
    assert mapped.activity_label == "pick_red_box"
    assert mapped.confidence == event.confidence and mapped.event_id == event.event_id
    assert mapped.metadata["mapping_semantics"] == "demo_proxy"
    assert mapped.metadata["original_activity"] == "touch_object"
    assert event.activity_label == "touch_object"
    resources.close()


def test_missing_weights_and_bad_vocabulary_are_actionable(tmp_path, capsys):
    assert main(["--source", "0", "--model", str(tmp_path / "absent.pt")]) == 2
    assert "YOLO model not found" in capsys.readouterr().err
    assert main(["--synthetic", "--scenario", "fusion", "--log", str(tmp_path / "log.jsonl")]) == 2
    assert "HAR cannot produce" in capsys.readouterr().err


def test_output_paths_cannot_overwrite_configs(tmp_path):
    assert main(["--synthetic", "--log", str(ROOT / "configs/runtime.yaml")]) == 2
    same = str(tmp_path / "same.jsonl")
    assert main(["--synthetic", "--log", same, "--diagnostics", same]) == 2


def test_headless_core_runs_without_gui_or_network(monkeypatch, tmp_path):
    import sys
    def forbidden(*args, **kwargs):
        raise AssertionError("outbound network disabled")
    monkeypatch.setattr(socket, "create_connection", forbidden)
    monkeypatch.setattr(socket.socket, "connect", forbidden)
    monkeypatch.setitem(sys.modules, "PySide6", None)
    assert main(["--synthetic", "--log", str(tmp_path / "offline.jsonl")]) == 0
