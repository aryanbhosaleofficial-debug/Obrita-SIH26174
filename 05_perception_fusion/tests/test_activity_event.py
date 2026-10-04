"""
Tests for ActivityEvent assembly (Module 05).

Implementation status:
    Scaffold only. Every test below is skipped until the component exists.
    Remove the module-level skip marker when implementing the tests.

Required test cases:
1. Output is an instance of shared.schemas.activity_event.ActivityEvent.
2. start_frame_id <= end_frame_id and both are set.
3. One continuous activity produces one event.
4. Activity labels come from the configured label set.
5. Fusion does not judge procedure order (that is the Procedure FSM).
"""

import pytest

pytestmark = pytest.mark.skip(reason="Scaffold only: implementation pending")


def test_uses_shared_schema():
    """Output is an instance of shared.schemas.activity_event.ActivityEvent."""
    raise NotImplementedError("Test not written yet")


def test_start_end_frames_set():
    """start_frame_id <= end_frame_id and both are set."""
    raise NotImplementedError("Test not written yet")


def test_no_duplicate_events():
    """One continuous activity produces one event."""
    raise NotImplementedError("Test not written yet")


def test_labels_match_procedure_vocabulary():
    """Activity labels come from the configured label set."""
    raise NotImplementedError("Test not written yet")


def test_no_procedure_validation_in_fusion():
    """Fusion does not judge procedure order (that is the Procedure FSM)."""
    raise NotImplementedError("Test not written yet")
