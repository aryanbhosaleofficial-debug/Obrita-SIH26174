"""Reviewed repair regressions; object tracks here are injected, not camera claims."""

from dataclasses import replace
from pathlib import Path

import pytest
from yolo.alerts.contracts import VoiceConfig
from yolo.alerts.manager import ERRORS
from yolo.core.contracts import BoundingBox, Detection, DetectionFrame
from yolo.procedure.assistant import ProcedureAssistant
from yolo.procedure.contracts import ConfirmedAction, ProcedureDefinition
from yolo.procedure.fast_actions import (
    FastClassifier,
    FastConfig,
    HomeRegion,
    load_fast_config,
)
from yolo.procedure.markdown_loader import load_procedure
from yolo.semantic.contracts import SemanticResult, SemanticStatus, default_actions

SAMPLE = Path(__file__).resolve().parents[1] / "examples/red_yellow_procedure.md"


def calibration():
    return FastConfig(
        home_regions={
            "red_box": HomeRegion(0, 0, 0.25, 1),
            "yellow_box": HomeRegion(0.75, 0, 1, 1),
        },
        work_regions={
            "red_box": HomeRegion(0.4, 0, 0.65, 1),
            "yellow_box": HomeRegion(0.4, 0, 0.65, 1),
        },
        work_dwell_frames=3,
    )


def frame(i, red=0.1, yellow=0.9):
    return DetectionFrame(
        i,
        i / 30,
        1000,
        500,
        [
            Detection(
                index,
                name,
                0.9,
                BoundingBox(x * 1000 - 20, 200, x * 1000 + 20, 240),
                index + 1,
                True,
            )
            for index, name, x in ((2, "red_box", red), (3, "yellow_box", yellow))
        ],
    )


def assistant(definition=None):
    return ProcedureAssistant(
        definition or load_procedure(SAMPLE),
        default_actions(),
        fast_config=calibration(),
        voice_config=VoiceConfig(enabled=False),
    )


def test_f1_yellow_pick_carry_place_actual_classifier_has_no_false_violation():
    full = load_procedure(SAMPLE)
    definition = ProcedureDefinition(
        "Yellow only",
        tuple(replace(step, index=i + 1) for i, step in enumerate(full.steps[3:])),
    )
    app = assistant(definition)
    try:
        for i, yellow in enumerate(
            [0.9] + [0.7] * 3 + [0.6, 0.56, 0.52, 0.48, 0.45] + [0.9] * 3
        ):
            app.observe(frame(i, yellow=yellow))
        records = list(app.log.records)
        assert app.state.status == "COMPLETED" and app.state.current_step_index == 2
        assert [r["observed"] for r in records if r["event"] == "STEP_COMPLETED"] == [
            "PICK_YELLOW",
            "PLACE_YELLOW",
        ]
        assert any(
            r["event"] == "NON_PROCEDURAL_ACTION" and r["action"] == "MANIPULATE_YELLOW"
            for r in records
        )
        assert not any(r["event"] in ERRORS for r in records)
        assert not any(
            r["event"] == "alert_queued" and r["alert_type"] in ERRORS for r in records
        )
    finally:
        app.close()


def test_f1_confirmed_and_semantic_incidental_actions_are_log_only():
    app = assistant()
    try:
        app.accept_confirmed(
            ConfirmedAction("PICK_RED", "red_box", 1, 1, "injected", app.clock())
        )
        before = app.state
        event = app.accept_confirmed(
            ConfirmedAction(
                "MANIPULATE_YELLOW", "yellow_box", 2, 2, "injected", app.clock()
            )
        )
        assert event.event == "NON_PROCEDURAL_ACTION" and app.state == before
        semantic = SemanticResult(
            "MANIPULATE_YELLOW", "yellow_box", SemanticStatus.READY, 3 / 30, 3, 1
        )
        app.observe(frame(3), semantic)
        assert app.state == before
        assert "MANIPULATE_YELLOW" in default_actions()
    finally:
        app.close()


def test_f1_other_procedure_can_legitimately_require_manipulate_yellow():
    full = load_procedure(SAMPLE)
    middle = replace(
        full.steps[1],
        index=2,
        step_id="manipulate_yellow",
        action="MANIPULATE_YELLOW",
        object_name="yellow_box",
    )
    definition = ProcedureDefinition(
        "Yellow manipulation",
        (replace(full.steps[3], index=1), middle, replace(full.steps[4], index=3)),
    )
    app = assistant(definition)
    try:
        for i, name in enumerate(("PICK_YELLOW", "MANIPULATE_YELLOW", "PLACE_YELLOW")):
            assert (
                app.accept_confirmed(
                    ConfirmedAction(name, "yellow_box", i, i, "injected", app.clock())
                ).event
                == "STEP_COMPLETED"
            )
        assert app.state.status == "COMPLETED"
    finally:
        app.close()


def test_f3_full_fast_sequence_with_work_dwell_and_incidental_yellow_motion():
    app = assistant()
    positions = (
        [(0.1, 0.9)]
        + [(0.3, 0.9)] * 3
        + [(x, 0.9) for x in (0.46, 0.5, 0.54, 0.57, 0.59)]
        + [(0.1, 0.9)] * 3
        + [(0.1, 0.7)] * 3
        + [(0.1, x) for x in (0.6, 0.56, 0.52, 0.48, 0.45)]
        + [(0.1, 0.9)] * 3
    )
    try:
        for i, (red, yellow) in enumerate(positions):
            app.observe(frame(i, red, yellow))
        assert app.state.status == "COMPLETED"
        events = list(app.log.records)
        assert [r["observed"] for r in events if r["event"] == "STEP_COMPLETED"] == [
            s.action for s in app.definition.steps
        ]
        assert not any(r["event"] in ERRORS for r in events)
    finally:
        app.close()


def test_f3_carry_outside_work_then_place_is_one_skip_without_qwen():
    app = assistant()
    try:
        for i, x in enumerate([0.1] + [0.3] * 3 + [0.7, 0.72, 0.74, 0.73] + [0.1] * 10):
            app.observe(frame(i, red=x))
        violations = [r for r in app.log.records if r["event"] in ERRORS]
        assert len(violations) == 1 and violations[0]["event"] == "SKIPPED_STEP"
        assert (
            app.state.next_action == "MANIPULATE_RED"
            and app.state.current_step_index == 1
        )
        assert not any(
            r.get("action") == "MANIPULATE_RED"
            for r in app.log.records
            if r["event"] == "action_candidate"
        )
    finally:
        app.close()


def test_f3_work_dwell_needs_motion_and_consecutive_evidence():
    fast = FastClassifier(calibration())
    fast.classify(frame(0))
    fast.acknowledge(fast.classify(frame(1, red=0.3)))
    for i in range(2, 10):
        assert fast.classify(frame(i, red=0.5)).action == "UNCERTAIN"
    assert fast.classify(frame(10, red=0.56)).action == "MANIPULATE_RED"
    # Leaving the work zone or missing a source frame resets the dwell anchor.
    assert fast.classify(frame(11, red=0.7)).action == "UNCERTAIN"
    assert fast.classify(frame(12, red=0.5)).action == "UNCERTAIN"
    assert fast.classify(frame(14, red=0.56)).action == "UNCERTAIN"


def test_f3_work_config_validation_and_legacy_coverage(tmp_path):
    with pytest.raises(ValueError):
        replace(calibration(), work_dwell_frames=0)
    with pytest.raises(ValueError):
        replace(calibration(), work_regions={"red_box": HomeRegion(0.1, 0, 0.5, 1)})
    bad = tmp_path / "bad.yaml"
    bad.write_text(
        "fast: {home_regions: {}, work_regions: {red_box: [0.4, 0, 0.6, 1]}}"
    )
    with pytest.raises(ValueError):
        load_fast_config(bad, default_actions())
    legacy = FastClassifier(FastConfig(home_regions=calibration().home_regions))
    assert legacy.coverage(load_procedure(SAMPLE)) == {
        "PICK_RED": True,
        "MANIPULATE_RED": False,
        "PLACE_RED": True,
        "PICK_YELLOW": True,
        "PLACE_YELLOW": True,
    }
    assert all(FastClassifier(calibration()).coverage(load_procedure(SAMPLE)).values())


def test_f6_missing_and_partial_calibration_warns_and_logs_coverage(caplog):
    for config in (None, FastConfig(home_regions=calibration().home_regions)):
        app = ProcedureAssistant(
            load_procedure(SAMPLE),
            default_actions(),
            fast_config=config,
            voice_config=VoiceConfig(enabled=False),
        )
        try:
            assert "may exceed the 1.5 s target" in caplog.text
            coverage = next(
                r for r in app.log.records if r["event"] == "fast_path_coverage"
            )
            assert coverage["actions"]["MANIPULATE_RED"] is False
            assert any(r["event"] == "fast_path_uncalibrated" for r in app.log.records)
        finally:
            app.close()
    caplog.clear()
    app = assistant()
    try:
        assert all(app.fast_coverage.values()) and not caplog.records
    finally:
        app.close()


def test_f6_roi_interior_must_survive_boundary_margin():
    with pytest.raises(ValueError, match="no usable interior"):
        FastConfig(home_regions={"red_box": HomeRegion(0, 0, 0.01, 1)})
