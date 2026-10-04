"""
Tests for coordinate restoration (Module 02).

Implementation status:
    Scaffold only. Every test below is skipped until the component exists.
    Remove the module-level skip marker when implementing the tests.

Required test cases:
1. No padding.
2. Horizontal letterbox padding.
3. Vertical letterbox padding.
4. Bounding box touching image edge.
5. Invalid bounding box.
6. Letterbox followed by restore returns the original box (within rounding).
"""

import pytest

pytestmark = pytest.mark.skip(reason="Scaffold only: implementation pending")


def test_no_padding():
    """No padding."""
    raise NotImplementedError("Test not written yet")


def test_horizontal_letterbox_padding():
    """Horizontal letterbox padding."""
    raise NotImplementedError("Test not written yet")


def test_vertical_letterbox_padding():
    """Vertical letterbox padding."""
    raise NotImplementedError("Test not written yet")


def test_bbox_touching_image_edge():
    """Bounding box touching image edge."""
    raise NotImplementedError("Test not written yet")


def test_invalid_bbox():
    """Invalid bounding box."""
    raise NotImplementedError("Test not written yet")


def test_letterbox_restore_round_trip():
    """Letterbox followed by restore returns the original box (within rounding)."""
    raise NotImplementedError("Test not written yet")
