"""
Tests for hand inference and handedness (Module 03, Teammate 3).

Implementation status:
    Scaffold only. Every test below is skipped until the component exists.
    Remove the module-level skip marker when implementing the tests.

Required test cases:
1. Hand landmarks are mapped back to original-frame pixels.
2. Handedness respects the camera mirroring flag.
3. A one-frame left/right swap is corrected.
4. A hand far from both wrists is rejected.
"""

import pytest

pytestmark = pytest.mark.skip(reason="Scaffold only: implementation pending")


def test_hand_landmarks_in_original_frame():
    """Hand landmarks are mapped back to original-frame pixels."""
    raise NotImplementedError("Test not written yet")


def test_handedness_respects_mirroring():
    """Handedness respects the camera mirroring flag."""
    raise NotImplementedError("Test not written yet")


def test_handedness_swap_corrected():
    """A one-frame left/right swap is corrected."""
    raise NotImplementedError("Test not written yet")


def test_implausible_hand_rejected():
    """A hand far from both wrists is rejected."""
    raise NotImplementedError("Test not written yet")
