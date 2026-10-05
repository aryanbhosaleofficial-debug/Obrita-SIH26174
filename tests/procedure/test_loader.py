from copy import deepcopy
from dataclasses import replace
from pathlib import Path
import pytest
import yaml

from procedure import ProcedureFSM, load_procedure

ROOT = Path(__file__).resolve().parents[2]


def payload():
    return yaml.safe_load((ROOT / "procedures/red_yellow_box.yaml").read_text())


def load(tmp_path, value):
    path = tmp_path / "procedure.yaml"
    path.write_text(yaml.safe_dump(value), encoding="utf-8")
    return load_procedure(path)


def test_valid_yaml_and_legacy_schema(tmp_path):
    definition = load(tmp_path, payload())
    assert definition.experiment_id == "red_yellow_box" and len(definition.steps) == 4
    assert definition.steps[1].timeout_s == 30
    legacy = load_procedure(ROOT / "procedures/demo_experiment.yaml", ROOT / "configs")
    assert [s.id for s in legacy.steps] == ["step_01", "step_02"]


@pytest.mark.parametrize("field", ["id", "name", "version"])
def test_missing_experiment_fields(tmp_path, field):
    data = payload()
    del data["experiment"][field]
    with pytest.raises(ValueError, match=field):
        load(tmp_path, data)


@pytest.mark.parametrize("field", ["id", "description", "expected_activity", "target_object"])
def test_missing_step_fields(tmp_path, field):
    data = payload()
    del data["steps"][0][field]
    with pytest.raises(ValueError):
        load(tmp_path, data)


@pytest.mark.parametrize("value", [[], None, {}, "steps"])
def test_invalid_steps(tmp_path, value):
    data = payload()
    data["steps"] = value
    with pytest.raises(ValueError, match="steps"):
        load(tmp_path, data)


def test_duplicate_ids_and_ambiguous_action_pairs(tmp_path):
    data = payload()
    data["steps"][1]["id"] = "step_1"
    with pytest.raises(ValueError, match="Duplicate step"):
        load(tmp_path, data)
    data = payload()
    data["steps"][1]["expected_activity"] = "pick_red_box"
    with pytest.raises(ValueError, match="Ambiguous"):
        load(tmp_path, data)
    data["steps"][1]["target_object"] = "yellow_box"
    assert load(tmp_path, data)  # same verb on a different object is unambiguous
    data["steps"][0]["target_object"] = None
    with pytest.raises(ValueError, match="Ambiguous"):
        load(tmp_path, data)


def test_alternate_events_validate_and_match(tmp_path, event):
    data = payload()
    data["vocabulary"]["activities"].append("grasp_red_box")
    data["steps"][0]["alternate_activities"] = ["grasp_red_box"]
    fsm = ProcedureFSM(definition=load(tmp_path, data))
    fsm.start()
    result = fsm.process(event(0, activity_label="grasp_red_box"))
    assert result.completed_steps == ("step_1",)
    data["steps"][1]["alternate_activities"] = ["grasp_red_box"]
    with pytest.raises(ValueError, match="Ambiguous"):
        load(tmp_path, data)


@pytest.mark.parametrize("order", [0, 2, True, "1"])
def test_invalid_order(tmp_path, order):
    data = payload()
    data["steps"][0]["order"] = order
    with pytest.raises(ValueError, match="order"):
        load(tmp_path, data)


@pytest.mark.parametrize("key,value", [("optional", "false"), ("description", " "),
    ("timeout_s", -1), ("expected_activity", "undeclared"), ("target_object", "undeclared"),
    ("alternate_activities", "bad"), ("unexpected_field", True)])
def test_invalid_step_values(tmp_path, key, value):
    data = payload()
    data["steps"][0][key] = value
    with pytest.raises(ValueError):
        load(tmp_path, data)


@pytest.mark.parametrize("rule", [{"action": "reverse_physical_action"}, {"action": "pause", "extra": True},
                                  {"action": "pause", "message": ""}, "pause"])
def test_invalid_recovery(tmp_path, rule):
    data = payload()
    data["steps"][0]["recovery"]["wrong_order"] = rule
    with pytest.raises(ValueError):
        load(tmp_path, data)


@pytest.mark.parametrize("key,value", [("confirmation_frames", 1), ("confirmation_frames", True),
    ("min_confidence", float("nan")), ("allow_missing_confidence", "true"),
    ("require_identity", 1), ("max_gap_s", 0), ("history_limit", 0), ("dedup_limit", 0),
    ("alert_cooldown_s", -1), ("ignored_actions", ["pick_red_box"]), ("unknown_field", 3)])
def test_invalid_event_policy(tmp_path, key, value):
    data = payload()
    data["event_policy"][key] = value
    with pytest.raises(ValueError):
        load(tmp_path, data)


def test_missing_file_and_unsafe_yaml_fail_clearly(tmp_path):
    with pytest.raises(FileNotFoundError):
        load_procedure(tmp_path / "missing.yaml")
    path = tmp_path / "unsafe.yaml"
    path.write_text("!!python/object/apply:os.system ['echo forbidden']", encoding="utf-8")
    with pytest.raises(ValueError, match="Invalid procedure YAML"):
        load_procedure(path)


def test_programmatic_definition_validated(definition):
    with pytest.raises(ValueError):
        ProcedureFSM(definition=replace(definition, steps=()))
    with pytest.raises(ValueError, match="Ambiguous"):
        ProcedureFSM(definition=replace(definition, steps=(definition.steps[0], replace(definition.steps[0], step_id="other"))))
