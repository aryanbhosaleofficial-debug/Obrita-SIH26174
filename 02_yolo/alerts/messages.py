"""Deterministic procedure speech text and stable cache keys (no voice backend)."""

ERRORS = {"SKIPPED_STEP", "WRONG_ORDER", "UNEXPECTED_ACTION", "STEP_TIMEOUT"}
CRITICAL = ("SKIPPED_STEP", "WRONG_ORDER", "UNEXPECTED_ACTION", "STEP_TIMEOUT")
PROCEDURE_KEY = "_procedure"  # step IDs cannot start with "_"
SUCCESS_TEXT = "Correct. Continue."
COMPLETED_TEXT = "Procedure complete."


def step_message(step, kind):
    if kind == "SKIPPED_STEP":
        return f"Step {step.index} was skipped. {step.warning}"
    prefixes = {
        "WRONG_ORDER": "Wrong order.",
        "UNEXPECTED_ACTION": "Unexpected action.",
        "STEP_TIMEOUT": f"Step {step.index} timed out.",
        "NEXT_STEP": "Next step.",
    }
    return f"{prefixes[kind]} {step.instruction}"


def message_entries(definition):
    """Every fixed message a procedure can speak, keyed by step_id/kind.

    Critical warnings come first so warm-up prepares them before prompts.
    """
    entries = []
    for kinds in (CRITICAL, ("NEXT_STEP",)):
        for step in definition.steps:
            for kind in kinds:
                if kind == "STEP_TIMEOUT" and step.timeout_ms is None:
                    continue
                entries.append(
                    (f"{step.step_id}/{kind}", kind, step_message(step, kind))
                )
    entries.append((f"{PROCEDURE_KEY}/SUCCESS", "SUCCESS", SUCCESS_TEXT))
    entries.append((f"{PROCEDURE_KEY}/COMPLETED", "COMPLETED", COMPLETED_TEXT))
    return entries


def procedure_messages(definition, config):
    enabled = {kind: config.speak_errors for kind in CRITICAL} | {
        "NEXT_STEP": config.speak_next_step,
        "COMPLETED": config.speak_next_step,
        "SUCCESS": config.speak_success,
    }
    return tuple(
        dict.fromkeys(
            text for _, kind, text in message_entries(definition) if enabled[kind]
        )
    )
