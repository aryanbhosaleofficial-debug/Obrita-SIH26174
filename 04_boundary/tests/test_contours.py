"""
Tests for contour extraction and validation (Module 04).

Implementation status:
    Scaffold only. Every test below is skipped until the component exists.
    Remove the module-level skip marker when implementing the tests.

Required test cases:
1. Contours are offset back to original-frame pixels.
2. Association picks the contour overlapping the target box.
3. Contours below configured area limits are rejected.
4. Resampled contour has the configured point count / spacing.
"""

import pytest

pytestmark = pytest.mark.skip(reason="Scaffold only: implementation pending")


def test_contour_offset_to_original_frame():
    """Contours are offset back to original-frame pixels."""
    raise NotImplementedError("Test not written yet")


def test_association_picks_target():
    """Association picks the contour overlapping the target box."""
    raise NotImplementedError("Test not written yet")


def test_small_contour_rejected():
    """Contours below configured area limits are rejected."""
    raise NotImplementedError("Test not written yet")


def test_resampling_uniform():
    """Resampled contour has the configured point count / spacing."""
    raise NotImplementedError("Test not written yet")
