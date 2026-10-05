from dataclasses import replace
import pytest

from procedure import ProcedureFSM
from procedure.contracts import DecisionType as D, ProcedureState as State, RecoveryAction as R, RecoveryRule


def configured(definition, action, key="wrong_order", message=None):
    first = replace(definition.steps[0], recovery=((key, RecoveryRule(action, message)),))
    return replace(definition, steps=(first, *definition.steps[1:]))


def test_recovery_completes_missing_step_then_continues(fsm, event):
    fsm.process(event(0))
    skip = fsm.process(event(2))
    assert skip.recovery_action == R.PERFORM_MISSING_STEP
    assert "step_2" in skip.message and skip.next_step_id == "step_2"
    assert fsm.process(event(1)).decision == D.VALID
    assert fsm.snapshot().recovery_action is None
    assert fsm.process(event(2)).decision == D.VALID
    assert fsm.process(event(3)).procedure_state == State.COMPLETED


def test_default_uncertain_consequences_require_operator_review(definition, event):
    first = replace(definition.steps[0], recovery=())
    fsm = ProcedureFSM(definition=replace(definition, steps=(first, *definition.steps[1:])))
    fsm.start()
    result = fsm.process(event(2))
    assert result.recovery_action == R.MANUAL_REVIEW
    assert "Pause and verify" in result.message and result.next_instruction is None
    assert fsm.process(event(0)).decision == D.IGNORED
    assert not fsm.completed_steps
    fsm.resume()
    assert fsm.process(event(0)).decision == D.VALID


@pytest.mark.parametrize("action", list(R))
def test_policy_never_silently_advances_or_undoes(definition, event, action):
    fsm = ProcedureFSM(definition=configured(definition, action))
    fsm.start()
    result = fsm.process(event(2))
    assert result.recovery_action == action
    assert not fsm.completed_steps and fsm.current_index == 0
    assert not any(word in result.message.lower() for word in ("undo", "put back", "reverse"))
    if action == R.RESTART_REQUIRED:
        with pytest.raises(ValueError, match="reset"):
            fsm.resume()
    elif action in (R.PAUSE, R.MANUAL_REVIEW):
        assert fsm.process(event()).decision == D.IGNORED
        fsm.resume()
        assert fsm.process(event()).decision == D.VALID
    else:
        assert fsm.process(event()).decision == D.VALID


def test_configured_message_is_used_verbatim(definition, event):
    message = "Pause at the marked demo station and ask the operator to verify."
    fsm = ProcedureFSM(definition=configured(definition, R.MANUAL_REVIEW, message=message))
    fsm.start()
    assert fsm.process(event(2)).message == message


def test_repeat_policy_belongs_to_completed_step(definition, event):
    fsm = ProcedureFSM(definition=configured(definition, R.PAUSE, key="repeated"))
    fsm.start()
    fsm.process(event())
    result = fsm.process(event())
    assert result.decision == D.REPEATED_ACTION
    assert result.procedure_state == State.PAUSED and result.current_step_id == "step_2"
    assert fsm.completed_steps == ["step_1"]


def test_same_warning_cooldown_state_transition_and_reset(fsm, event):
    assert fsm.process(event(2)).should_speak
    assert not fsm.process(event(2)).should_speak
    assert not fsm.process(event(2)).should_speak
    assert fsm.process(event(2, frame=7)).should_speak
    fsm.process(event(0))
    assert fsm.process(event(2)).should_speak  # different expected step
    fsm.reset()
    fsm.start()
    assert fsm.process(event(2, frame=1)).should_speak
