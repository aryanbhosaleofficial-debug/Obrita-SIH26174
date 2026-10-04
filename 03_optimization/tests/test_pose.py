"""
Tests for pose inference and validation (Module 03, Teammate 3).

Implementation status:
    Scaffold only. Every test below is skipped until the component exists.
    Remove the module-level skip marker when implementing the tests.

Required test cases:
1. Pose landmarks are mapped from ROI back to original-frame pixels.
2. Landmarks below the visibility threshold are flagged invalid.
3. No person track results in an explicit 'no pose' status.
4. z values are treated as relative depth, never as metric units.
"""

import pytest

pytestmark = pytest.mark.skip(reason="Scaffold only: implementation pending")


def test_landmarks_in_original_frame_pixels():
    """Pose landmarks are mapped from ROI back to original-frame pixels."""
    raise NotImplementedError("Test not written yet")


def test_low_visibility_landmarks_flagged():
    """Landmarks below the visibility threshold are flagged invalid."""
    raise NotImplementedError("Test not written yet")


def test_no_operator_no_pose():
    """No person track results in an explicit 'no pose' status."""
    raise NotImplementedError("Test not written yet")


def test_z_documented_as_relative():
    """z values are treated as relative depth, never as metric units."""
    raise NotImplementedError("Test not written yet")
