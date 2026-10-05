"""Injected evidence tests, never claims of real camera action recognition."""

from dataclasses import replace
from pathlib import Path

import cv2
import numpy as np
import pytest
from yolo.alerts.contracts import VoiceConfig
from yolo.core.contracts import BoundingBox, Detection, DetectionFrame
from yolo.procedure.assistant import ProcedureAssistant
from yolo.procedure.contracts import ConfirmedAction
from yolo.procedure.fast_actions import (
    FastClassifier,
    FastConfig,
    HomeRegion,
    load_fast_config,
)
from yolo.procedure.fusion import ActionConfirmation, ActionFusion
from yolo.procedure.markdown_loader import (
    ProcedureError,
    load_procedure,
    parse_procedure,
)
from yolo.procedure.validator import ProcedureValidator
from yolo.semantic.contracts import SemanticResult, SemanticStatus, default_actions
from yolo.standalone_cli import main
from yolo.visualization.procedure_overlay import render_procedure

OWNER = Path(__file__).resolve().parents[1]
SAMPLE = OWNER / "examples/red_yellow_procedure.md"


class Clock:
    value = 100.0

    def __call__(self):
        return self.value


def action(name, frame=1, clock=None):
    return ConfirmedAction(
        name,
        default_actions().get(name),
        frame,
        float(frame),
        "injected_test",
        (clock or Clock())(),
    )


def objects(frame, x=20, y=50, *, present=True, track=1, persistent=True):
    return DetectionFrame(
        frame,
        frame / 30,
        100,
        100,
        [
            Detection(
                2,
                "red_box",
                0.9,
                BoundingBox(x - 5, y - 5, x + 5, y + 5),
                track,
                persistent,
            )
        ]
        if present
        else [],
    )


def config():
    return FastConfig(home_regions={"red_box": HomeRegion(0, 0, 0.4, 1)})


def test_markdown_valid_unicode_timeout_and_custom_allowlist():
    text = SAMPLE.read_text(encoding="utf-8")
    definition = parse_procedure(
        text.replace("Pick up the red box.", "Pick the red box: café ✓.", 1).replace(
            "- id: pick_red", "- timeout_ms: 5000\n- id: pick_red", 1
        )
    )
    assert definition.name == "Red Yellow Box Demo" and len(definition.steps) == 5
    assert definition.steps[0].timeout_ms == 5000
    assert definition.steps[0].confirmation_frames == 3
    assert "café" in definition.steps[0].instruction
    assert load_procedure(SAMPLE).steps[0].timeout_ms is None
    custom = dict(default_actions(), TURN_RED="red_box")
    assert (
        parse_procedure(text.replace("PICK_RED", "TURN_RED"), custom).steps[0].action
        == "TURN_RED"
    )


@pytest.mark.parametrize(
    "old,new",
    [
        ("# Experiment:", "# Procedure:"),
        ("## Step 2", "## Step 1"),
        ("## Step 2", "## Step two"),
        ("- id: manipulate_red", "- id: pick_red"),
        ("- action: PICK_RED\n", ""),
        ("- action: PICK_RED", "- action: UNKNOWN"),
        ("- action: PICK_RED", "- action: NONE"),
        ("- action: PICK_RED", "- action: PICK_RED\n- action: PICK_RED"),
        ("- instruction: Pick up the red box.", "- instruction: "),
        ("- confirmation_frames: 3", "- confirmation_frames: 0"),
        ("- confirmation_frames: 3", "- confirmation_frames: -1"),
        ("- confirmation_frames: 3", "- confirmation_frames: true"),
        ("- id: pick_red", "- timeout_ms: -1\n- id: pick_red"),
        ("- id: pick_red", "- timeout_ms: 0\n- id: pick_red"),
        ("- object: red_box", "- object: yellow_box"),
        ("- id: pick_red", "- extra: unsupported\n- id: pick_red"),
    ],
)
def test_markdown_rejects_corrupted_definition(old, new):
    with pytest.raises(ProcedureError):
        parse_procedure(SAMPLE.read_text().replace(old, new, 1))


def test_markdown_bounds_and_empty_definition():
    for text in ("", "# Experiment: Empty", "x" * 65537):
        with pytest.raises(ProcedureError):
            parse_procedure(text)


def test_validator_correct_sequence_completion_and_reset():
    validator = ProcedureValidator(load_procedure(SAMPLE))
    for i, step in enumerate(validator.definition.steps):
        result = validator.observe(action(step.action, i))
        assert result.event == "STEP_COMPLETED"
        assert validator.state.current_step_index == i + 1
    assert (
        validator.state.status == "COMPLETED" and validator.state.next_step_id is None
    )
    assert validator.observe(action("PLACE_YELLOW", 6)).event == "REPEATED_ACTION"
    validator.reset()
    assert (
        validator.state.current_step_index == 0 and not validator.state.completed_steps
    )


def test_validator_skip_wrong_order_repeat_unexpected_and_noops():
    validator = ProcedureValidator(load_procedure(SAMPLE))
    assert validator.observe(action("PICK_YELLOW")).event == "WRONG_ORDER"
    assert validator.state.current_step_index == 0
    validator.observe(action("PICK_RED", 2))
    event = validator.observe(action("PLACE_RED", 3))
    assert event.event == "SKIPPED_STEP" and event.skipped_steps == ("manipulate_red",)
    assert (
        validator.state.current_step_index == 1
        and validator.state.next_action == "MANIPULATE_RED"
    )
    assert validator.observe(action("PICK_RED", 4)).event == "REPEATED_ACTION"
    assert (
        validator.observe(action("MANIPULATE_YELLOW", 5)).event == "UNEXPECTED_ACTION"
    )
    assert validator.observe(action("NONE", 6)) is None
    assert validator.observe(action("UNCERTAIN", 7)) is None
    assert validator.state.current_step_index == 1


def test_timeout_explicit_once_only_and_reset():
    clock = Clock()
    definition = load_procedure(SAMPLE)
    validator = ProcedureValidator(definition, clock=clock)
    clock.value += 10000
    assert validator.tick(1, 1) is None  # no invented timeout
    definition = replace(
        definition,
        steps=(replace(definition.steps[0], timeout_ms=5000), *definition.steps[1:]),
    )
    validator = ProcedureValidator(definition, clock=clock)
    clock.value += 4.99
    assert validator.tick(2, 2) is None
    clock.value += 0.02
    assert validator.tick(3, 3).event == "STEP_TIMEOUT"
    assert validator.tick(4, 4) is None and validator.current == 0
    validator.reset()
    assert validator.tick(5, 5) is None


def test_confirmation_consecutive_frames_gaps_and_episode_latch():
    confirm = ActionConfirmation()
    args = ("PICK_RED", "red_box")
    for i in (0, 1):
        assert confirm.observe(*args, i, i, 3, "fast") is None
    assert confirm.observe(*args, 3, 3, 3, "fast") is None  # gap restarts count
    assert confirm.observe(*args, 4, 4, 3, "fast") is None
    assert confirm.observe(*args, 5, 5, 3, "fast").action == "PICK_RED"
    assert confirm.observe(*args, 6, 6, 3, "fast") is None
    for i in (7, 8, 9):
        confirm.observe("UNCERTAIN", None, i, i, 3, "fast")
    assert confirm.observe(*args, 10, 10, 1, "fast") is not None


def test_fast_rules_calibrated_transitions_not_absence_or_vertical_direction():
    fast = FastClassifier(
        replace(config(), work_regions={"red_box": HomeRegion(0.7, 0, 1, 1)})
    )
    assert fast.classify(objects(0)).action == "UNCERTAIN"
    pick = fast.classify(objects(1, x=60))
    assert pick.action == "PICK_RED"
    fast.acknowledge(pick)
    assert fast.classify(objects(2, x=80)).action == "UNCERTAIN"
    assert fast.classify(objects(3, x=81)).action == "UNCERTAIN"
    manipulate = fast.classify(objects(4, x=85))
    assert manipulate.action == "MANIPULATE_RED"
    fast.acknowledge(manipulate)
    place = fast.classify(objects(5, x=20))
    assert place.action == "PLACE_RED"
    fast.acknowledge(place)
    assert fast.classify(objects(6, present=False)).action == "UNCERTAIN"
    assert fast.classify(objects(7, x=80)).action == "UNCERTAIN"
    assert FastClassifier().classify(objects(0)).action == "UNCERTAIN"
    rotated = FastClassifier(
        FastConfig(home_regions={"red_box": HomeRegion(0, 0.6, 1, 1)})
    )
    rotated.classify(objects(0, x=50, y=80))
    assert rotated.classify(objects(1, x=50, y=30)).action == "PICK_RED"


@pytest.mark.parametrize(
    "changes", [{"track": None}, {"persistent": False}, {"track": 2}]
)
def test_fast_identity_failure_and_reacquisition_are_uncertain(changes):
    fast = FastClassifier(config())
    fast.classify(objects(0))
    assert fast.classify(objects(1, x=80, **changes)).action == "UNCERTAIN"


def test_reference_motion_and_boundary_jitter_are_uncertain():
    fast = FastClassifier(replace(config(), reference_object="main_box"))
    frame = objects(0)
    frame.detections.append(
        Detection(1, "main_box", 0.9, BoundingBox(0, 0, 20, 20), 3, True)
    )
    fast.classify(frame)
    frame = objects(1, x=80)
    frame.detections.append(
        Detection(1, "main_box", 0.9, BoundingBox(20, 0, 40, 20), 3, True)
    )
    assert fast.classify(frame).action == "UNCERTAIN"
    plain = FastClassifier(config())
    plain.classify(objects(0))
    assert plain.classify(objects(1, x=40)).action == "UNCERTAIN"


def test_fast_config_is_validated(tmp_path):
    assert not load_fast_config(None, default_actions()).home_regions
    assert load_fast_config(
        OWNER / "examples/demo_fast_rules.yaml", default_actions()
    ).home_regions
    for roi in ((-1, 0, 1, 1), (0.5, 0, 0.4, 1), (0, 0, float("nan"), 1)):
        with pytest.raises(ValueError):
            HomeRegion(*roi)
    bad = tmp_path / "bad.yaml"
    bad.write_text("fast: {home_regions: {unmapped: [0, 0, 1, 1]}}")
    with pytest.raises(ValueError):
        load_fast_config(bad, default_actions())


def test_semantic_fusion_distinct_events_staleness_failure_and_disagreement():
    fusion = ActionFusion(default_actions())
    first = SemanticResult("PICK_RED", "red_box", SemanticStatus.READY, 1, 1, 1)
    assert fusion.semantic_action(first, 3, current_timestamp_s=1) == (None, None)
    for _ in range(10):
        assert fusion.semantic_action(first, 3, current_timestamp_s=1) == (None, None)
    fusion.semantic_action(
        replace(first, frame_id=2, timestamp_s=2, event_id=2), 3, current_timestamp_s=2
    )
    confirmed, _ = fusion.semantic_action(
        replace(first, frame_id=3, timestamp_s=3, event_id=3), 3, current_timestamp_s=3
    )
    assert confirmed.action == "PICK_RED" and confirmed.source == "semantic"
    fast = FastClassifier(config())
    fast.classify(objects(4))
    candidate = fast.classify(objects(5, x=80))
    assert fusion.fast_action(candidate, 1).source == "fast"
    disagree = replace(first, action="PLACE_RED", event_id=4, frame_id=4, timestamp_s=4)
    assert (
        fusion.semantic_action(disagree, 1, current_timestamp_s=5)[1]["event"]
        == "vlm_disagreement"
    )
    assert fusion.semantic_action(
        replace(first, status=SemanticStatus.VLM_ERROR, event_id=5),
        1,
        current_timestamp_s=5,
    ) == (None, None)
    assert fusion.semantic_action(
        replace(first, event_id=6, frame_id=6), 1, current_timestamp_s=100
    ) == (None, None)


def test_assistant_fast_skip_without_qwen_and_nonmutating_hud():
    assistant = ProcedureAssistant(
        load_procedure(SAMPLE),
        default_actions(),
        fast_config=config(),
        voice_config=VoiceConfig(enabled=False),
    )
    try:
        assistant.observe(objects(0))
        for i in range(1, 4):
            assistant.observe(objects(i, x=60))
        assert assistant.state.current_step_index == 1
        for i in range(4, 7):
            assistant.observe(objects(i, x=20))
        assert (
            assistant.state.status == "SKIPPED_STEP"
            and assistant.state.current_step_index == 1
        )
        assert any(r["event"] == "SKIPPED_STEP" for r in assistant.log.records)
        pixels = np.zeros((240, 320, 3), np.uint8)
        display = render_procedure(pixels, assistant.state, voice_status="DISABLED")
        assert not np.any(pixels) and np.any(display)
        assert np.array_equal(display[:240], pixels)
        assert display.shape == (436, 320, 3)
        assistant.reset()
        assert (
            assistant.state.current_step_index == 0 and not assistant.classifier.states
        )
    finally:
        assistant.close()


def test_cli_procedure_and_invalid_definition_fail_before_detector(
    tmp_path, monkeypatch
):
    image = tmp_path / "input.png"
    assert cv2.imwrite(str(image), np.zeros((240, 320, 3), np.uint8))
    detector_config = tmp_path / "none.yaml"
    detector_config.write_text("detector: {backend: none}")
    logs, events = tmp_path / "frames.jsonl", tmp_path / "events.jsonl"
    assert (
        main(
            [
                "--source",
                str(image),
                "--config",
                str(detector_config),
                "--procedure",
                str(SAMPLE),
                "--no-vlm",
                "--no-voice",
                "--no-display",
                "--jsonl",
                str(logs),
                "--events-jsonl",
                str(events),
            ]
        )
        == 0
    )
    assert '"voice_status": "DISABLED"' in logs.read_text()
    assert "procedure_loaded" in events.read_text()
    bad = tmp_path / "bad.md"
    bad.write_text("invalid")
    monkeypatch.setattr(
        "yolo.standalone_cli.DetectorPipeline",
        lambda *a, **k: pytest.fail("must validate procedure first"),
    )
    assert main(["--source", str(image), "--procedure", str(bad), "--no-display"]) == 2
