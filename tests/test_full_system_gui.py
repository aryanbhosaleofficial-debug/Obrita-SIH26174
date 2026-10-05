"""Observe the production runner, real runtime and queued bridge at Qt widgets.

Only inference backends/semantic actions are synthetic. No GUI mock is allowed.
"""
import os
import sys
import threading

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
import numpy as np
import pytest

pytest.importorskip("PySide6")
from PySide6.QtCore import QThread, QTimer, Qt
from PySide6.QtTest import QTest

from GUI.orbita_gui.adapters import snapshot_from_dict
from GUI.orbita_gui.bridge import PipelineBridge
from GUI.orbita_gui.main_window import OrbitaWindow, make_app
from integration.full_cli import build_runtime, options
from integration.full_gui import run_gui
from integration.full_system import FullSystemRuntime


def production(monkeypatch, tmp_path, scenario="correct", *, configure=None, receive=None):
    import integration.full_gui
    import GUI.orbita_gui.main_window as windows
    app = make_app([])
    observed = {"snapshots": [], "frames": [], "threads": []}
    monkeypatch.setitem(sys.modules, "GUI.orbita_gui.mock", None)

    class Window(OrbitaWindow):
        def __init__(self, **kwargs):
            super().__init__(**kwargs)
            observed["window"] = self
            update, set_frame = self.console.update_snapshot, self.console.set_frame
            def snapshot(value):
                assert QThread.currentThread() == app.thread()
                observed["snapshots"].append(value)
                update(value)
                if receive:
                    receive(self, value)
            def frame(value):
                assert QThread.currentThread() == app.thread()
                identity = self.console.snapshot.frame_id
                # Source marker in an unobscured corner proves BGR frame/state pairing.
                assert value.pixelColor(319, 239).blue() == identity % 256
                observed["frames"].append(identity)
                set_frame(value)
            self.console.update_snapshot, self.console.set_frame = snapshot, frame

    monkeypatch.setattr(windows, "OrbitaWindow", Window)
    args = options(["--synthetic", "--scenario", scenario, "--gui", "--log", str(tmp_path / "events.jsonl")])
    def build(*a, **kw):
        observed["threads"].append(threading.current_thread().name)
        runtime, frames, resources = build_runtime(*a, **kw)
        assert isinstance(runtime, FullSystemRuntime)
        assert isinstance(runtime.gui, PipelineBridge)
        assert sys.modules["GUI.orbita_gui.mock"] is None
        process = runtime.pipeline.process
        def marked(packet):
            packet.image[239, 319] = (packet.frame_id % 256, 0, 0)
            return process(packet)
        runtime.pipeline.process = marked
        observed["runtime"] = runtime
        args.max_frames = None  # finite source EOF, rather than the CLI frame limit
        runtime.realtime_fps = 200.
        if configure:
            configure(runtime, observed["window"])
        return runtime, frames, resources

    watchdog = QTimer()
    watchdog.setSingleShot(True)
    watchdog.timeout.connect(app.quit)
    watchdog.start(10000)
    try:
        observed["summary"] = run_gui(build, args)
        assert watchdog.isActive(), "Qt runner did not exit on its own"
    finally:
        watchdog.stop()
        observed["window"].close()
    return observed


@pytest.mark.parametrize("scenario,state,decision", [
    ("correct", "completed", "valid"),
    ("wrong-order", "recovery_required", "wrong_order"),
    ("skip", "recovery_required", "skipped_step"),
    ("recovery", "completed", "skipped_step"),
    ("repeated", "in_progress", "valid"),
])
def test_production_scenarios_reach_qt_widgets(monkeypatch, tmp_path, scenario, state, decision):
    seen = production(monkeypatch, tmp_path, scenario)
    summary, window, snapshots = seen["summary"], seen["window"], seen["snapshots"]
    assert summary["error"] is None and summary["exit_reason"] == "eof"
    assert summary["frames"] == 72 and summary["procedure_state"] == state
    assert seen["threads"] == ["full-system-inference"]
    assert seen["frames"] and all(s.source_id and s.session_id for s in snapshots)
    assert any(s.decision == decision for s in snapshots)
    final = snapshots[-1]
    assert final.frame_id == 71 and final.timestamp_s == 71 / 30
    assert final.procedure_state == state
    assert window.console.status.msg.text() == final.status_text
    assert window.console.proc.steps == final.steps
    assert window.console.next.text.text() == final.next_step.text
    assert not window.console.demo_row.isVisible()
    assert not final.scene.simulated and final.scene.overlays_rendered
    assert final.scene.objects[0].conf == .9
    assert final.log and final.log_path == str(seen["runtime"].log.path)
    assert window.console.log_panel.right.toolTip() == final.log_path
    assert {"Preprocessing", "Boundary", "Activity Adapter", "Pose/Hands"} <= final.system_health.keys()
    assert all(s.spoken == "" for s in snapshots)  # no playback subsystem selected
    if state == "completed":
        assert all(s.state == "done" for s in final.steps)
        assert final.next_step.number == "" and final.next_step.progress == 1
        assert any(a.level == "advisory" for a in final.alerts)
    if scenario in ("wrong-order", "skip", "recovery"):
        recoveries = [s for s in snapshots if s.recovery_action]
        assert recoveries and any(s.state == "wrong" for s in recoveries[0].steps)
        assert recoveries[0].next_step.text == recoveries[0].status_text
        assert recoveries[0].alerts
        if scenario == "recovery":
            assert final.recovery_action is None
            assert any(r["event"] == "recovery_completed" for r in seen["runtime"].log.records)
    if scenario == "repeated":
        assert summary["completed_steps"] == ["step_1"]
        assert any(r.get("activity_label") == "pick_red_box" for r in seen["runtime"].log.records)


def test_burst_keeps_one_wakeup_and_newest_pair_on_qt_thread():
    app = make_app([])
    window = OrbitaWindow(show_demo_controls=False)
    bridge = PipelineBridge()
    bridge.attach(window.console)
    wakeups, delivered = [], []
    bridge.update_ready.connect(lambda: wakeups.append(1), Qt.DirectConnection)
    bridge.snapshot_ready.connect(lambda s: delivered.append((s.frame_id, QThread.currentThread())))
    def burst():
        for fid in range(1000):
            bridge.push_update(np.full((2, 2, 3), fid % 256, np.uint8),
                               {"frame_id": fid, "stamp": str(fid), "status_text": str(fid)})
        bridge.push_snapshot({"frame_id": 999, "stamp": "999", "status_text": "newest"})
    worker = threading.Thread(target=burst)
    worker.start()
    worker.join(timeout=5)
    assert not worker.is_alive() and wakeups == [1]
    assert window.console.camera.frame is None  # worker cannot directly touch widgets
    for _ in range(3):
        app.processEvents()
    assert delivered == [(999, app.thread())]
    assert window.console.status.msg.text() == "newest"
    assert window.console.camera.stamp == "999"
    assert window.console.camera.frame.pixelColor(0, 0).blue() == 999 % 256
    window.close()


@pytest.mark.parametrize("key", [Qt.Key_Q, Qt.Key_Escape])
def test_gui_close_keys_stop_worker(monkeypatch, tmp_path, key):
    closed = []
    def receive(window, snapshot):
        if not closed:
            closed.append(True)
            QTimer.singleShot(0, lambda: QTest.keyClick(window, key))
    seen = production(monkeypatch, tmp_path, receive=receive)
    assert seen["summary"]["exit_reason"] == "stop_requested"
    assert seen["summary"]["frames"] < 72
    assert seen["runtime"].closed and seen["runtime"].pipeline.chain._closed
    assert not any(t.name == "full-system-inference" for t in threading.enumerate())


def test_controls_and_voice_toggle_cross_worker_queue(monkeypatch, tmp_path):
    commands = [(Qt.Key_Space, "paused"), (Qt.Key_C, "ready"),
                (Qt.Key_R, "ready"), (Qt.Key_A, "aborted"), (Qt.Key_C, "aborted")]
    sent, muted = [], []
    class Voice:
        enabled, status = True, "READY"
        def enqueue(self, alert):
            return True
        def mute(self, value):
            muted.append((value, threading.current_thread().name))
            self.enabled = value
        def reset(self):
            pass
        def close(self):
            pass
        @property
        def manager(self):
            return self
    def configure(runtime, window):
        runtime.voice = Voice()
        runtime.consumer.alert_sink = runtime._alert
        # Observe every frame for the lifecycle test, regardless of repaint cadence.
        runtime.realtime_fps = 30.
    def receive(window, snapshot):
        if len(sent) < len(commands):
            key, state = commands[len(sent)]
            if sent:
                assert snapshot.procedure_state == commands[len(sent) - 1][1]
            sent.append(key)
            QTest.keyClick(window, key)
        elif not muted:
            window.console.header.voice.click()
    seen = production(monkeypatch, tmp_path, configure=configure, receive=receive)
    records = seen["runtime"].log.records
    assert [r["control"] for r in records if r["event"] == "control_applied" and r["control"] != "voice"] == ["pause", "resume", "reset", "abort"]
    assert any(r["event"] == "control_rejected" and r["control"] == "resume" for r in records)
    assert muted == [(False, "full-system-inference")]
    assert seen["summary"]["procedure_state"] == "aborted"
    assert all(not s.spoken for s in seen["snapshots"])  # accepted requests never claim playback


def test_worker_exception_is_visible_and_exits(monkeypatch, tmp_path):
    def configure(runtime, window):
        process = runtime.pipeline.process
        def fail(packet):
            if packet.frame_id == 5:
                raise RuntimeError("injected perception failure")
            return process(packet)
        runtime.pipeline.process = fail
    seen = production(monkeypatch, tmp_path, configure=configure)
    assert seen["summary"]["exit_reason"] == "error"
    assert "injected perception failure" in seen["window"].console.status.msg.text()
    assert seen["snapshots"][-1].status_level == "warning"
    assert seen["runtime"].closed


@pytest.mark.parametrize("output", ["Recording", "Streaming", "Voice", "Logging"])
def test_optional_failure_is_visible_without_killing_fsm(monkeypatch, tmp_path, output):
    def configure(runtime, window):
        class Broken:
            error = "injected output failure"
            written = dropped = 0
            url = "local test output"
            enabled = True
            status = "VOICE_UNAVAILABLE"
            def submit(self, *args):
                raise OSError(self.error)
            def close(self):
                pass
        if output == "Recording":
            runtime.recorder = Broken()
        elif output == "Streaming":
            runtime.stream = Broken()
        elif output == "Voice":
            runtime.voice = Broken()
            runtime.health_errors["Voice"] = Broken.error
        else:
            class Disk:
                def write(self, value):
                    raise OSError("injected output failure")
            runtime.log.log._file = Disk()
    seen = production(monkeypatch, tmp_path, configure=configure)
    final = seen["snapshots"][-1]
    assert seen["summary"]["procedure_state"] == "completed" and seen["summary"]["error"] is None
    assert final.system_health[output] == "DEGRADED"
    assert any(output in alert.text for alert in final.alerts)
    if output in ("Recording", "Streaming"):
        assert not final.recording and not final.lan_streaming
        chip = seen["window"].console.header.rec if output == "Recording" else seen["window"].console.header.lan
        assert "DEGRADED" in chip.text


def test_adapter_missing_optional_data_has_no_demo_or_confidence():
    snap = snapshot_from_dict({"next_step": {"text": "waiting", "future": True},
        "steps": [{"id": "one", "text": "One", "future": True}], "scene": None,
        "tracking": {"deep": "diagnostic only"}, "met_seconds": None})
    assert snap.confidence is None and snap.next_step.confidence is None
    assert not snap.scene.simulated and not snap.scene.objects
    assert snap.frame_id is None and snap.steps[0].state == "pending"


def test_optional_skip_is_rendered_from_fsm(monkeypatch, tmp_path):
    from dataclasses import replace
    from procedure import ProcedureFSM, ProcedureIntegration
    def configure(runtime, window):
        definition = runtime.fsm.definition
        steps = list(definition.steps)
        steps[1] = replace(steps[1], optional=True)
        runtime.fsm = ProcedureFSM(definition=replace(definition, steps=tuple(steps)))
        runtime.consumer = ProcedureIntegration(runtime.fsm, log_sink=runtime._guidance_log)
    seen = production(monkeypatch, tmp_path, "skip", configure=configure)
    final = seen["snapshots"][-1]
    assert final.steps[1].state == "skipped"
    assert final.steps[2].state == "done" and final.steps[3].state == "active"
    assert final.recovery_action is None
