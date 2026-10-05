from dataclasses import asdict
import json
from pathlib import Path
import subprocess
import sys
import pytest

from procedure import ProcedureFSM, ProcedureIntegration
from procedure.contracts import DecisionType as D, ProcedureState as State
from procedure.integration import activity_from_dict, gui_snapshot, to_alert, voice_definition
from procedure.procedure_loader import ProcedureDefinition, ProcedureStep

ROOT = Path(__file__).resolve().parents[2]


def test_real_module05_outputs_flow_into_procedure_without_inference_assets():
    from integration.chain import PerceptionChain
    from integration.milestone import MilestonePipeline
    from integration.synthetic import configure, scene
    from shared.config import PipelineConfig
    frames, detector, hands = scene()
    definition = ProcedureDefinition("fusion_demo", "Fusion semantic boundary", "1", (
        ProcedureStep("touch", "Touch the sample container.", "touch_object", "sample_container"),
        ProcedureStep("move", "Move the sample container.", "move_object", "sample_container")))
    consumer = ProcedureIntegration(ProcedureFSM(definition=definition))
    consumer.start()
    chain = PerceptionChain(configure(PipelineConfig()), detector=detector, hand_tracker=hands)
    with MilestonePipeline(chain) as pipeline:
        decisions = [consumer.process(pipeline.process(frame).activity) for frame in frames]
    valid = [d for d in decisions if d.decision == D.VALID]
    assert len(valid) == 2
    assert [d.observed_action for d in valid] == ["touch_object", "move_object"]
    assert valid[-1].procedure_state == State.COMPLETED
    assert valid[-1].completed_steps == ("touch", "move")
    assert all(d.source_id == frames[d.frame_id].source_id for d in valid)
    assert all(d.timestamp_s == frames[d.frame_id].timestamp_s for d in valid)
    assert valid[0].metadata["upstream"]["confirmed"] is True


def test_gui_adapter_uses_actual_snapshot_contract(fsm, event):
    pytest.importorskip("PySide6")
    from GUI.orbita_gui.adapters import snapshot_from_dict
    result = fsm.process(event(2))
    dictionary = gui_snapshot(result)
    snapshot = snapshot_from_dict(dictionary)
    assert snapshot.steps[0].state == "wrong"
    assert snapshot.next_step.number == "step_1"
    assert snapshot.confidence == .9
    assert not snapshot.scene.simulated and not snapshot.spoken
    assert snapshot.alerts[0].text == result.message


def test_dispatch_reuses_alert_event_and_actual_event_log(tmp_path, definition, event):
    from yolo.alerts.contracts import AlertEvent
    from yolo.procedure.event_log import EventLog
    gui, alerts = [], []
    path = tmp_path / "procedure.jsonl"
    log = EventLog(path)
    try:
        consumer = ProcedureIntegration(ProcedureFSM(definition=definition), gui_sink=gui.append,
                                         alert_sink=alerts.append, log_sink=log.emit, clock=lambda: 50.)
        consumer.start()
        first = consumer.process(event(2))
        consumer.process(event(2))
        consumer.process(event(2))
        assert len(alerts) == 2  # start + one warning, not one warning per frame
        assert isinstance(alerts[-1], AlertEvent)
        assert alerts[-1].alert_type == "WRONG_ORDER"
        assert alerts[-1].timestamp_s == first.timestamp_s
        assert alerts[-1].violation_confirmed_timestamp == 50.
        assert len(log.records) == 2
        assert not consumer.last_dispatch_errors
    finally:
        log.close()
    assert [r["decision"] for r in map(json.loads, path.read_text().splitlines())] == ["state_changed", "wrong_order"]


def test_voice_config_adapter_does_not_create_another_fsm(definition):
    from yolo.alerts.contracts import VoiceConfig
    from yolo.alerts.manager import AlertManager
    adapted = voice_definition(definition)
    assert [s.step_id for s in adapted.steps] == [s.id for s in definition.steps]
    assert adapted.steps[1].timeout_ms == 30000
    manager = AlertManager(adapted, VoiceConfig(enabled=False), tts=object(), player=object())
    try:
        assert manager.status == "DISABLED" and manager._thread is None
        assert manager.messages
    finally:
        manager.close()


def test_sink_failure_is_reported_and_does_not_double_apply(definition, event):
    def fail(value):
        raise RuntimeError("sink unavailable")
    logged = []
    consumer = ProcedureIntegration(ProcedureFSM(definition=definition), gui_sink=fail, log_sink=logged.append)
    consumer.start()
    incoming = event()
    result = consumer.process(incoming)
    assert result.decision == D.VALID and consumer.last_dispatch_errors
    assert logged[-1]["decision"] == D.VALID
    assert consumer.process(incoming).decision == D.DUPLICATE
    assert consumer.fsm.completed_steps == ["step_1"]


def test_reset_resets_downstream_alert_cooldown(definition, event):
    resets = []
    consumer = ProcedureIntegration(ProcedureFSM(definition=definition), reset_alerts=lambda: resets.append(True))
    consumer.start()
    consumer.process(event())
    consumer.reset()
    assert resets == [True] and not consumer.fsm.completed_steps


def test_alert_construction_failure_does_not_starve_gui_or_log(definition, event):
    gui, logs = [], []
    consumer = ProcedureIntegration(ProcedureFSM(definition=definition), gui_sink=gui.append,
        log_sink=logs.append, alert_sink=lambda payload: None, clock=lambda: float("nan"))
    consumer.start()
    result = consumer.process(event())
    assert result.decision == D.VALID and gui and logs
    assert consumer.last_dispatch_errors[0].startswith("alert:")


def test_json_event_round_trip_preserves_none_confidence_and_metadata(event):
    original = event(confidence=None)
    restored = activity_from_dict(json.loads(json.dumps(asdict(original))))
    assert restored == original
    assert restored.confidence is None
    with pytest.raises(ValueError):
        activity_from_dict({"extra": "unknown schema"})


@pytest.mark.parametrize("scenario,expected", [("correct", "completed"), ("wrong-order", "recovery_required"),
    ("skip", "recovery_required"), ("repeated", "in_progress"), ("recovery", "completed")])
def test_demo_scenarios(scenario, expected):
    completed = subprocess.run([sys.executable, "-m", "procedure.demo", "--procedure", "red_yellow_box",
                                "--scenario", scenario, "--json"], cwd=ROOT, capture_output=True, text=True, timeout=20)
    assert completed.returncode == 0, completed.stderr
    rows = [json.loads(line) for line in completed.stdout.splitlines()]
    assert rows[-1]["procedure_state"] == expected
    assert rows[-1]["metadata"]["upstream"]["synthetic"]


def test_cli_replays_actual_event_contract(tmp_path, definition):
    from procedure.demo import synthetic_events
    path = tmp_path / "events.jsonl"
    path.write_text("\n".join(json.dumps(asdict(e)) for e in synthetic_events(definition)), encoding="utf-8")
    completed = subprocess.run([sys.executable, "-m", "procedure.demo", "--events", str(path), "--json"],
                               cwd=ROOT, capture_output=True, text=True, timeout=20)
    assert completed.returncode == 0, completed.stderr
    assert json.loads(completed.stdout.splitlines()[-1])["procedure_state"] == "completed"


def test_offline_core_does_not_import_inference_or_gui_backends():
    code = "import sys; sys.modules.update({k:None for k in ('cv2','mediapipe','ultralytics','PySide6','pyttsx3')}); from procedure import ProcedureFSM, load_procedure; f=ProcedureFSM(definition=load_procedure('procedures/red_yellow_box.yaml')); f.start(); print(f.state.value)"
    completed = subprocess.run([sys.executable, "-c", code], cwd=ROOT, capture_output=True, text=True, timeout=20)
    assert completed.returncode == 0 and completed.stdout.strip() == "ready", completed.stderr


def test_missing_config_or_invalid_event_file_is_actionable(tmp_path, capsys):
    from procedure.demo import main
    assert main(["--procedure", str(tmp_path / "missing.yaml")]) == 2
    bad = tmp_path / "bad.jsonl"
    bad.write_text("not-json", encoding="utf-8")
    assert main(["--events", str(bad)]) == 2
    assert "Event line 1" in capsys.readouterr().err


def test_live_cli_optional_procedure_consumes_real_fusion_events(tmp_path):
    diagnostics = tmp_path / "frames.jsonl"
    events = tmp_path / "events.jsonl"
    guidance = tmp_path / "guidance.jsonl"
    completed = subprocess.run([sys.executable, "scripts/run_fusion.py", "--synthetic",
        "--procedure", "procedures/fusion_touch_move.yaml", "--output", str(diagnostics),
        "--events", str(events), "--guidance", str(guidance)], cwd=ROOT,
        capture_output=True, text=True, timeout=30)
    assert completed.returncode == 0, completed.stderr
    records = [json.loads(line) for line in guidance.read_text().splitlines()]
    assert records[0]["procedure_state"] == "ready"
    valid = [row for row in records if row["decision"] == "valid"]
    assert [row["observed_action"] for row in valid] == ["touch_object", "move_object"]
    assert valid[-1]["procedure_state"] == "completed"
    emitted = {row["event_id"]: row for row in map(json.loads, events.read_text().splitlines())}
    assert all(row["confidence"] == emitted[row["event_id"]]["confidence"] for row in valid)
    last = json.loads(diagnostics.read_text().splitlines()[-1])
    assert last["procedure"]["completed_steps"] == ["touch", "move"]


def test_live_cli_rejects_output_overwriting_procedure(tmp_path):
    from integration.cli import main
    procedure = tmp_path / "procedure.yaml"
    original = (ROOT / "procedures/fusion_touch_move.yaml").read_text()
    procedure.write_text(original)
    assert main(["--synthetic", "--procedure", str(procedure), "--guidance", str(procedure)]) == 2
    assert procedure.read_text() == original
    assert main(["--synthetic", "--guidance", str(tmp_path / "unused.jsonl")]) == 2


def test_synthetic_guidance_is_labelled_in_gui(definition):
    from procedure.demo import synthetic_events
    fsm = ProcedureFSM(definition=definition)
    fsm.start()
    assert gui_snapshot(fsm.process(next(synthetic_events(definition))))["scene"]["simulated"]
