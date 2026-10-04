"""
Tests for evidence fusion (Module 05).

Implementation status:
    Scaffold only. Every test below is skipped until the component exists.
    Remove the module-level skip marker when implementing the tests.

Required test cases:
1. Packets are matched by frame_id and target_track_id.
2. Packets with error status are rejected.
3. Confidence values outside [0, 1] are rejected.
4. Missing evidence is not treated as negative evidence.
5. Fusion weights are read from configuration.
"""

import pytest

pytestmark = pytest.mark.skip(reason="Scaffold only: implementation pending")


def test_packets_matched_by_frame_and_track():
    """Packets are matched by frame_id and target_track_id."""
    raise NotImplementedError("Test not written yet")


def test_invalid_status_rejected():
    """Packets with error status are rejected."""
    raise NotImplementedError("Test not written yet")


def test_confidence_range_validated():
    """Confidence values outside [0, 1] are rejected."""
    raise NotImplementedError("Test not written yet")


def test_missing_evidence_not_negative():
    """Missing evidence is not treated as negative evidence."""
    raise NotImplementedError("Test not written yet")


def test_weights_from_config():
    """Fusion weights are read from configuration."""
    raise NotImplementedError("Test not written yet")
