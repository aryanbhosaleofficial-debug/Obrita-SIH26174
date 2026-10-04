"""
Tests for skeleton generation and landmark processing (Module 03, Teammate 3).

Implementation status:
    Scaffold only. Every test below is skipped until the component exists.
    Remove the module-level skip marker when implementing the tests.

Required test cases:
1. All connection pairs reference valid landmark indices.
2. Bones with a missing endpoint are skipped.
3. Interpolated landmarks are flagged as interpolated.
4. Gaps longer than the configured span are not interpolated.
"""

import pytest

pytestmark = pytest.mark.skip(reason="Scaffold only: implementation pending")


def test_connections_reference_valid_indices():
    """All connection pairs reference valid landmark indices."""
    raise NotImplementedError("Test not written yet")


def test_missing_landmark_bones_skipped():
    """Bones with a missing endpoint are skipped."""
    raise NotImplementedError("Test not written yet")


def test_interpolated_landmarks_flagged():
    """Interpolated landmarks are flagged as interpolated."""
    raise NotImplementedError("Test not written yet")


def test_interpolation_span_limited():
    """Gaps longer than the configured span are not interpolated."""
    raise NotImplementedError("Test not written yet")
