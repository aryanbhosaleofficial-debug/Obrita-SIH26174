"""Optional assistant HUD on another display copy; never draws on AI pixels."""

import textwrap

import cv2
from yolo.visualization.renderer import VisualizationError


def voice_backend_line(summary):
    """Truthful backend line: probe results, never an assumed backend."""
    if not summary:
        return None
    fixed = summary.get("fixed_messages") or {}
    fixed_text = ", ".join(f"{k.upper()} {v}" for k, v in sorted(fixed.items()))
    piper = summary.get("backends", {}).get("piper", "NOT_CONFIGURED")
    dynamic = summary.get("dynamic")
    return (
        f"Fixed: {fixed_text or 'NONE'} | Dynamic: "
        f"{dynamic.upper() if dynamic else 'NONE'} | PIPER: {piper}"
    )


def render_procedure(
    display, state, *, voice_status, warning_latency_ms=None, voice_backends=None
):
    try:
        height, width = display.shape[:2]
        # Fixed-size lower panel keeps boxes unobscured and writer dimensions
        # stable when status text or measured latency changes between frames.
        output = cv2.copyMakeBorder(
            display, 0, 196, 0, 0, cv2.BORDER_CONSTANT, value=(30, 30, 30)
        )
        lines = [
            f"Step: {min(state.current_step_index + 1, state.total_steps)}/{state.total_steps} {state.status}",
            f"Expected: {state.next_action or 'COMPLETE'}",
            f"Observed: {state.last_action}",
            f"Next: {textwrap.shorten(state.next_instruction or 'Procedure complete.', width=100)}",
            f"VOICE: {voice_status}",
        ]
        backend_line = voice_backend_line(voice_backends)
        if backend_line:
            lines.append(backend_line)
        if warning_latency_ms is not None:
            lines.append(
                f"Last warning start (device estimate): {warning_latency_ms:.0f} ms"
            )
        chars = max(20, width // 9)
        wrapped = [part for line in lines for part in textwrap.wrap(line, width=chars)]
        line_height = 18
        start = height
        for i, line in enumerate(wrapped[:10]):
            cv2.putText(
                output,
                line,
                (6, start + 15 + i * line_height),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.42,
                (255, 255, 255),
                1,
            )
        return output
    except (cv2.error, AttributeError, TypeError) as exc:
        raise VisualizationError(f"procedure overlay failed: {exc}") from exc
