"""
Tests for the full offline pipeline.

Implementation status:
    Scaffold only. Every test below is skipped until the component exists.
    Remove the module-level skip marker when implementing the tests.

Required test cases:
1. A recorded demo video in data/videos/ runs end-to-end without network access.
2. ActivityEvents are written to outputs/events/.
3. Procedure FSM reports correct / wrong-order / skipped steps for a scripted demo.
4. Per-module timing is measured and logged (no assumed targets).
"""

import pytest

pytestmark = pytest.mark.skip(reason="Scaffold only: implementation pending")


def test_recorded_video_end_to_end():
    """A recorded demo video in data/videos/ runs end-to-end without network access."""
    raise NotImplementedError("Test not written yet")


def test_events_written():
    """ActivityEvents are written to outputs/events/."""
    raise NotImplementedError("Test not written yet")


def test_procedure_outcomes():
    """Procedure FSM reports correct / wrong-order / skipped steps for a scripted demo."""
    raise NotImplementedError("Test not written yet")


def test_timing_measured():
    """Per-module timing is measured and logged (no assumed targets)."""
    raise NotImplementedError("Test not written yet")
