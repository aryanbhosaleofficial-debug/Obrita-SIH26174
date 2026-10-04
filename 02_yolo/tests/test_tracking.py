"""
Tests for tracking (Module 02).

Implementation status:
    Scaffold only. Every test below is skipped until the component exists.
    Remove the module-level skip marker when implementing the tests.

Required test cases:
1. Same object keeps the same track_id across consecutive frames.
2. Track becomes 'lost' after the configured number of missing frames.
3. A lost track that reappears is marked 'reacquired' with the same track_id.
4. Two crossing objects do not swap track_id (document if this is a known limitation).
5. A new object receives a new track_id.
"""

import pytest

pytestmark = pytest.mark.skip(reason="Scaffold only: implementation pending")


def test_track_id_persistent():
    """Same object keeps the same track_id across consecutive frames."""
    raise NotImplementedError("Test not written yet")


def test_track_lost_after_max_frames():
    """Track becomes 'lost' after the configured number of missing frames."""
    raise NotImplementedError("Test not written yet")


def test_track_reacquired():
    """A lost track that reappears is marked 'reacquired' with the same track_id."""
    raise NotImplementedError("Test not written yet")


def test_crossing_objects_keep_ids():
    """Two crossing objects do not swap track_id (document if this is a known limitation)."""
    raise NotImplementedError("Test not written yet")


def test_new_object_new_id():
    """A new object receives a new track_id."""
    raise NotImplementedError("Test not written yet")
