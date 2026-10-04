"""
Tests for detection filtering and validation (Module 02).

Implementation status:
    Scaffold only. Every test below is skipped until the component exists.
    Remove the module-level skip marker when implementing the tests.

Required test cases:
1. Detections below the configured threshold are removed.
2. Classes not allowed in configuration are removed.
3. Zero-area and non-finite boxes are rejected.
4. No detections still produce a valid, empty ObjectFrame.
5. Missing model file raises a clear error and never triggers a download.
"""

import pytest

pytestmark = pytest.mark.skip(reason="Scaffold only: implementation pending")


def test_confidence_threshold_filtering():
    """Detections below the configured threshold are removed."""
    raise NotImplementedError("Test not written yet")


def test_disallowed_classes_removed():
    """Classes not allowed in configuration are removed."""
    raise NotImplementedError("Test not written yet")


def test_invalid_boxes_rejected():
    """Zero-area and non-finite boxes are rejected."""
    raise NotImplementedError("Test not written yet")


def test_empty_detections_valid_object_frame():
    """No detections still produce a valid, empty ObjectFrame."""
    raise NotImplementedError("Test not written yet")


def test_missing_model_file_clear_error():
    """Missing model file raises a clear error and never triggers a download."""
    raise NotImplementedError("Test not written yet")
