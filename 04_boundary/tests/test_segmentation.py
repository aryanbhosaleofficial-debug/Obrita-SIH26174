"""
Tests for segmentation (Module 04).

Implementation status:
    Scaffold only. Every test below is skipped until the component exists.
    Remove the module-level skip marker when implementing the tests.

Required test cases:
1. HSV ranges are taken from configuration.
2. Small noise components are removed by mask cleanup.
3. An empty mask is reported, not treated as a valid boundary.
4. Segmentation does not modify the source frame.
"""

import pytest

pytestmark = pytest.mark.skip(reason="Scaffold only: implementation pending")


def test_hsv_ranges_from_config():
    """HSV ranges are taken from configuration."""
    raise NotImplementedError("Test not written yet")


def test_mask_cleanup_removes_noise():
    """Small noise components are removed by mask cleanup."""
    raise NotImplementedError("Test not written yet")


def test_empty_mask_reported():
    """An empty mask is reported, not treated as a valid boundary."""
    raise NotImplementedError("Test not written yet")


def test_source_frame_not_modified():
    """Segmentation does not modify the source frame."""
    raise NotImplementedError("Test not written yet")
