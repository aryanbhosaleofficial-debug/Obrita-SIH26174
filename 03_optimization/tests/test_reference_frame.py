"""
Tests for rack reference frame (Module 03, Teammate 3).

Implementation status:
    Scaffold only. Every test below is skipped until the component exists.
    Remove the module-level skip marker when implementing the tests.

Required test cases:
1. A valid ReferenceAnchor produces a valid RackReference.
2. Missing anchor marks the reference invalid (no silent camera-up fallback).
3. Original-frame -> rack-relative -> original-frame round trip is consistent.
4. Orientation changes when the rack rotates in the image, not with camera 'up'.
"""

import pytest

pytestmark = pytest.mark.skip(reason="Scaffold only: implementation pending")


def test_reference_from_anchor():
    """A valid ReferenceAnchor produces a valid RackReference."""
    raise NotImplementedError("Test not written yet")


def test_missing_anchor_invalid_reference():
    """Missing anchor marks the reference invalid (no silent camera-up fallback)."""
    raise NotImplementedError("Test not written yet")


def test_transform_round_trip():
    """Original-frame -> rack-relative -> original-frame round trip is consistent."""
    raise NotImplementedError("Test not written yet")


def test_orientation_relative_to_rack():
    """Orientation changes when the rack rotates in the image, not with camera 'up'."""
    raise NotImplementedError("Test not written yet")
