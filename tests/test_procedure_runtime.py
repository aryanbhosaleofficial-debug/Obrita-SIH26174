from procedure.fsm import ProcedureFSM, StepOutcome
from procedure.procedure_loader import load_procedure
from shared.schemas.activity_event import ActivityEvent


def test_load_procedure_accepts_demo_config():
    definition = load_procedure("procedures/demo_experiment.yaml", "configs")
    assert definition.experiment_id == "demo_experiment"
    assert [step.step_id for step in definition.steps] == ["step_01", "step_02"]


def test_fsm_accepts_expected_event_sequence():
    definition = load_procedure("procedures/demo_experiment.yaml", "configs")
    fsm = ProcedureFSM(steps=[step.as_dict() for step in definition.steps])

    event_1 = ActivityEvent(
        event_id="evt_1",
        activity_label="PLACEHOLDER_ACTIVITY",
        frame_id=10,
        timestamp_s=1.0,
        start_frame_id=10,
        end_frame_id=11,
        start_timestamp_s=1.0,
        end_timestamp_s=1.1,
        target_object_class="PLACEHOLDER_OBJECT",
        confidence=1.0,
    )
    outcome_1, _ = fsm.on_event(event_1)
    assert outcome_1 == StepOutcome.CORRECT

    event_2 = ActivityEvent(
        event_id="evt_2",
        activity_label="PLACEHOLDER_ACTIVITY_2",
        frame_id=20,
        timestamp_s=2.0,
        start_frame_id=20,
        end_frame_id=21,
        start_timestamp_s=2.0,
        end_timestamp_s=2.1,
        target_object_class="PLACEHOLDER_OBJECT_A",
        confidence=1.0,
    )
    outcome_2, next_step = fsm.on_event(event_2)
    assert outcome_2 == StepOutcome.CORRECT
    assert next_step is None
