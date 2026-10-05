from dataclasses import FrozenInstanceError, replace
import math
import pytest

from procedure import ProcedureFSM
from procedure.contracts import DecisionType as D, ProcedureState as State, StepState
from shared.enums.module_status import ModuleStatus


def test_explicit_start_and_correct_sequence(definition, event):
    fsm = ProcedureFSM(definition=definition)
    assert fsm.state == State.NOT_STARTED
    assert fsm.process(event()).decision == D.IGNORED
    start = fsm.start(source_id="camera", session_id="run")
    assert start.next_step_id == "step_1" and fsm.state == State.READY
    for index in range(4):
        result = fsm.process(event(index))
        assert result.decision == D.VALID
        assert result.completed_steps == tuple(s.id for s in definition.steps[:index + 1])
    assert fsm.state == State.COMPLETED
    assert result.next_step_id is result.next_instruction is result.current_step_id is None
    assert result.message == "Procedure complete."
    after = fsm.process(event(0))
    assert after.decision == D.COMPLETED and not after.should_speak


def test_wrong_order_at_start_and_skips_after_progress(fsm, event):
    wrong = fsm.process(event(2))
    assert wrong.decision == D.WRONG_ORDER
    assert wrong.matching_step_id == "step_3"
    assert wrong.skipped_steps == ("step_1", "step_2")
    assert wrong.expected_action == "pick_red_box" and wrong.current_step_index == 0
    assert not fsm.completed_steps
    fsm.process(event(0))
    skip = fsm.process(event(3))
    assert skip.decision == D.SKIPPED_STEP
    assert skip.skipped_steps == ("step_2", "step_3")
    assert fsm.completed_steps == ["step_1"] and fsm.current_index == 1
    assert all(s.state != StepState.COMPLETED for s in skip.step_states[1:])


def test_repeated_unknown_and_missing_target_do_not_advance(fsm, event):
    fsm.process(event())
    repeated = fsm.process(event())
    assert repeated.decision == D.REPEATED_ACTION and not repeated.should_speak
    assert fsm.process(event("scratch_head")).decision == D.UNEXPECTED_ACTION
    wrong_object = fsm.process(event(1, target_object_class="unrelated"))
    missing_object = fsm.process(event(1, target_object_class=None))
    assert wrong_object.decision == missing_object.decision == D.UNEXPECTED_ACTION
    assert fsm.completed_steps == ["step_1"]
    assert fsm.last_valid_action == "pick_red_box"


def test_duplicate_and_out_of_order_cannot_advance(fsm, event):
    first = event(frame=10)
    fsm.process(first)
    assert fsm.process(first).decision == D.DUPLICATE
    assert fsm.process(event(1, frame=11, event_id=first.event_id)).decision == D.DUPLICATE
    assert fsm.process(event(1, frame=9, event_id="stale")).decision == D.STALE_EVENT
    assert fsm.process(event(1, frame=12, timestamp=9, event_id="stale-time")).decision == D.STALE_EVENT
    assert fsm.process(event(1, frame=10, timestamp=20, event_id="same-frame")).decision == D.STALE_EVENT
    assert fsm.completed_steps == ["step_1"]
    assert fsm.process(event(1, frame=13, timestamp=21)).decision == D.VALID


@pytest.mark.parametrize("identity", [{"source": "other"}, {"session": "other"}])
def test_identity_change_requires_reset(fsm, event, identity):
    fsm.process(event())
    assert fsm.process(event(1, **identity)).decision == D.SESSION_MISMATCH
    assert fsm.completed_steps == ["step_1"]
    fsm.reset()
    fsm.start()
    assert fsm.process(event(0, **identity)).decision == D.VALID


def test_wrong_procedure_identity_rejected(fsm, event):
    incoming = event()
    incoming.metadata["procedure_id"] = "another-procedure"
    assert fsm.process(incoming).decision == D.SESSION_MISMATCH
    assert not fsm.completed_steps


@pytest.mark.parametrize("bad", [None, {}, "action"])
def test_wrong_input_type_is_recoverable(fsm, event, bad):
    assert fsm.process(bad).decision == D.INVALID_EVENT
    assert fsm.process(event()).decision == D.VALID


@pytest.mark.parametrize("change", [
    {"confidence": math.nan}, {"confidence": math.inf}, {"confidence": 1.1}, {"confidence": True},
    {"frame_id": -1}, {"frame_id": 1.5}, {"frame_id": True},
    {"timestamp_s": math.nan}, {"timestamp_s": -1}, {"end_timestamp_s": 0},
    {"start_frame_id": 9}, {"activity_label": None}, {"event_id": ""},
    {"metadata": []}, {"metadata": {}}, {"status": "ok"}, {"target_object_class": 4},
    {"target_object_track_id": []},
])
def test_invalid_fields_do_not_mutate_progress(fsm, event, change):
    assert fsm.process(replace(event(), **change)).decision == D.INVALID_EVENT
    assert fsm.current_index == 0 and fsm.state == State.READY


@pytest.mark.parametrize("flags", [{"confirmed": True}, {"confirmed": "true", "emitted": True},
                                   {"confirmed": False, "emitted": True}])
def test_invalid_confirmation_metadata(fsm, event, flags):
    value = event(raw=True)
    value.metadata.update(flags)
    assert fsm.process(value).decision == D.INVALID_EVENT


def test_upstream_confirmed_events_advance_once_and_nonemitted_do_not(fsm, event):
    value = event()
    assert fsm.process(value).decision == D.VALID
    continuous = event(1)
    continuous.metadata["emitted"] = False
    assert fsm.process(continuous).decision == D.PENDING_CONFIRMATION
    assert fsm.current_index == 1
    for _ in range(5):
        value = event(1)
        value.metadata.update(confirmed=False, emitted=False)
        assert fsm.process(value).decision == D.PENDING_CONFIRMATION
    assert fsm.current_index == 1  # never override explicit upstream rejection


def test_per_frame_predictions_require_consecutive_confirmation(fsm, event):
    assert fsm.process(event(raw=True)).decision == D.PENDING_CONFIRMATION
    second = event(raw=True)
    assert fsm.process(second).decision == D.PENDING_CONFIRMATION
    assert fsm.process(second).decision == D.DUPLICATE  # replay cannot add a hit
    assert fsm.process(event(raw=True)).decision == D.VALID
    for _ in range(8):
        assert fsm.process(event(raw=True)).decision == D.IGNORED
    assert len(fsm.completed_steps) == 1


@pytest.mark.parametrize("breaker", ["unknown", "low_confidence", "gap", "track", "invalid"])
def test_noise_or_gap_breaks_confirmation(fsm, event, breaker):
    fsm.process(event(raw=True))
    fsm.process(event(raw=True))
    if breaker == "unknown":
        fsm.process(event("unknown", raw=True))
    elif breaker == "low_confidence":
        fsm.process(event(raw=True, confidence=.1))
    elif breaker == "gap":
        assert fsm.process(event(raw=True, frame=20)).decision == D.PENDING_CONFIRMATION
    elif breaker == "track":
        fsm.process(event(raw=True, target_object_track_id=9))
    else:
        fsm.process(None)
    assert fsm.process(event(raw=True)).decision == D.PENDING_CONFIRMATION
    assert not fsm.completed_steps


@pytest.mark.parametrize("status", [ModuleStatus.NO_DETECTION, ModuleStatus.INVALID_INPUT, ModuleStatus.ERROR])
def test_bad_upstream_status_cannot_advance(fsm, event, status):
    assert fsm.process(event(status=status)).decision == D.IGNORED
    assert not fsm.completed_steps


def test_missing_confidence_is_preserved_and_requires_explicit_policy(definition, event):
    fsm = ProcedureFSM(definition=definition)
    fsm.start()
    assert fsm.process(event(confidence=None)).decision == D.IGNORED
    allowed = replace(definition, event_policy=replace(definition.event_policy, allow_missing_confidence=True))
    fsm = ProcedureFSM(definition=allowed)
    fsm.start()
    result = fsm.process(event(confidence=None))
    assert result.decision == D.VALID and result.confidence is None


def test_reset_clears_all_run_state(fsm, event):
    first = event()
    fsm.process(first)
    fsm.process(event(2))
    fsm.reset()
    snap = fsm.snapshot()
    assert snap.state == State.NOT_STARTED and not snap.completed_steps
    assert snap.last_valid_action is snap.last_event_id is snap.recovery_action is snap.session_id is None
    assert not fsm.history and not fsm._alerts and not fsm._seen
    assert fsm.last_confirmed_event is None
    fsm.start()
    assert fsm.process(first).decision == D.VALID


def test_pause_resume_abort_and_terminal_controls(fsm, event):
    fsm.pause()
    ignored = event()
    assert fsm.process(ignored).decision == D.IGNORED
    fsm.resume()
    assert fsm.process(ignored).decision == D.DUPLICATE
    assert fsm.process(event()).decision == D.VALID
    fsm.abort()
    assert fsm.process(event(1)).decision == D.IGNORED
    with pytest.raises(ValueError):
        fsm.resume()
    with pytest.raises(ValueError):
        fsm.start()
    assert fsm.completed_steps == ["step_1"]


def test_optional_skip_is_explicit_not_completed(definition, event):
    steps = list(definition.steps)
    steps[1] = replace(steps[1], optional=True)
    fsm = ProcedureFSM(definition=replace(definition, steps=tuple(steps)))
    fsm.start()
    fsm.process(event())
    result = fsm.process(event(2))
    assert result.decision == D.VALID and result.skipped_steps == ("step_2",)
    assert fsm.completed_steps == ["step_1", "step_3"]
    assert result.step_states[1].state == StepState.SKIPPED
    assert fsm.process(event(3)).procedure_state == State.COMPLETED


def test_snapshot_and_evidence_are_detached(fsm, event):
    incoming = event()
    result = fsm.process(incoming)
    incoming.metadata["test_evidence"]["retained"] = False
    assert result.metadata["upstream"]["test_evidence"]["retained"]
    snap = fsm.snapshot()
    with pytest.raises(FrozenInstanceError):
        snap.state = State.ERROR
    fsm.process(event(1))
    assert snap.completed_steps == ("step_1",)


def test_bounded_history_and_replay_after_cache_expiry(definition, event):
    policy = replace(definition.event_policy, history_limit=3, dedup_limit=2)
    fsm = ProcedureFSM(definition=replace(definition, event_policy=policy))
    fsm.start()
    first = event()
    fsm.process(first)
    for _ in range(10):
        fsm.process(event("unrelated"))
    assert len(fsm.history) == 3 and len(fsm._seen) == 2
    assert fsm.process(first).decision == D.STALE_EVENT
    assert fsm.completed_steps == ["step_1"]


def test_corrupt_cursor_fails_closed_and_reset_recovers(fsm, event):
    fsm._current_index = 999
    assert fsm.process(event()).decision == D.ERROR
    fsm.reset()
    fsm.start()
    assert fsm.process(event()).decision == D.VALID


@pytest.mark.parametrize("field,value", [("_current_index", 4), ("_states", None),
                                         ("_states", ["bad"] * 4), ("_completed", None)])
def test_corrupt_progress_fails_closed(fsm, event, field, value):
    setattr(fsm, field, value)
    result = fsm.process(event())
    assert result.decision == D.ERROR and result.next_instruction is None
    assert result.metadata["state_corrupt"]


def test_rejected_foreign_event_retains_its_own_identity(fsm, event):
    fsm.process(event())
    incoming = event(1, source="other-camera", session="other-run")
    result = fsm.process(incoming)
    assert result.source_id == "other-camera" and result.session_id == "other-run"
    assert result.timestamp_s == incoming.timestamp_s and result.frame_id == incoming.frame_id
    assert result.metadata["bound_source_id"] == "camera"
    assert fsm.snapshot().session_id == "run"
    assert result.should_display and result.should_speak


def test_pending_event_id_replay_with_new_frame_cannot_confirm(fsm, event):
    first = event(raw=True)
    assert fsm.process(first).decision == D.PENDING_CONFIRMATION
    assert fsm.process(event(raw=True, event_id=first.event_id)).decision == D.DUPLICATE
    assert fsm.process(event(raw=True)).decision == D.PENDING_CONFIRMATION
    assert not fsm.completed_steps


@pytest.mark.parametrize("frame,timestamp", [(20, 20.), (7, 20.)])
def test_new_occurrence_after_gap_requires_fresh_confirmation(fsm, event, frame, timestamp):
    for _ in range(3):
        result = fsm.process(event(raw=True))
    assert result.decision == D.VALID
    for _ in range(3):
        assert fsm.process(event(raw=True)).decision == D.IGNORED
    assert fsm.process(event(raw=True, frame=frame, timestamp=timestamp)).decision == D.PENDING_CONFIRMATION
    assert fsm.process(event(raw=True, frame=frame + 1, timestamp=timestamp + .1)).decision == D.PENDING_CONFIRMATION
    assert fsm.process(event(raw=True, frame=frame + 2, timestamp=timestamp + .2)).decision == D.REPEATED_ACTION
    assert fsm.completed_steps == ["step_1"]


@pytest.mark.parametrize("index", [-1, True, 0.5])
def test_legacy_next_step_rejects_bad_indices(index):
    from procedure.next_step import next_step, completion_message
    for helper in (next_step, completion_message):
        with pytest.raises(ValueError):
            helper([{"id": "one", "description": "Do the step"}], index)
