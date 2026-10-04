"""
Tests for gesture recognition (Module 03, Teammate 4).

Implementation status:
    Scaffold only. Every test below is skipped until the component exists.
    Remove the module-level skip marker when implementing the tests.

Required test cases:
1. Gesture labels are loaded from configuration.
2. Insufficient evidence yields 'unknown', not a guess.
3. A gesture is confirmed only after N-of-M frames.
4. Single-frame label flicker is suppressed by the temporal filter.
"""

import pytest

pytestmark = pytest.mark.skip(reason="Scaffold only: implementation pending")


def test_labels_loaded_from_config():
    """Gesture labels are loaded from configuration."""
    raise NotImplementedError("Test not written yet")


def test_insufficient_evidence_unknown():
    """Insufficient evidence yields 'unknown', not a guess."""
    raise NotImplementedError("Test not written yet")


def test_multi_frame_confirmation():
    """A gesture is confirmed only after N-of-M frames."""
    raise NotImplementedError("Test not written yet")


def test_flicker_suppressed():
    """Single-frame label flicker is suppressed by the temporal filter."""
    raise NotImplementedError("Test not written yet")
