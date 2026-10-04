"""
Tests for temporal boundary tracking (Module 04).

Implementation status:
    Scaffold only. Every test below is skipped until the component exists.
    Remove the module-level skip marker when implementing the tests.

Required test cases:
1. Static synthetic object yields STATIONARY.
2. Translating synthetic object yields MOVING.
3. Rotating synthetic object yields ROTATING (rack-relative).
4. Target track change resets boundary history.
5. State is confirmed only after N-of-M frames.
"""

import pytest

pytestmark = pytest.mark.skip(reason="Scaffold only: implementation pending")


def test_stationary_object():
    """Static synthetic object yields STATIONARY."""
    raise NotImplementedError("Test not written yet")


def test_translating_object():
    """Translating synthetic object yields MOVING."""
    raise NotImplementedError("Test not written yet")


def test_rotating_object():
    """Rotating synthetic object yields ROTATING (rack-relative)."""
    raise NotImplementedError("Test not written yet")


def test_target_change_resets_history():
    """Target track change resets boundary history."""
    raise NotImplementedError("Test not written yet")


def test_confirmation_required():
    """State is confirmed only after N-of-M frames."""
    raise NotImplementedError("Test not written yet")
