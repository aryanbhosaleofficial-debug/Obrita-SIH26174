"""
Tests for frame IDs, timestamps and synchronization (Module 01).

Implementation status:
    Scaffold only. Every test below is skipped until the component exists.
    Remove the module-level skip marker when implementing the tests.

Required test cases:
1. frame_id values are strictly increasing and never reused.
2. timestamp_s values are monotonic.
3. Packets with identical frame_id are matched.
4. Packets with different frame_id are never paired.
5. Frame buffer lookup of an evicted frame_id returns None.
"""

import pytest

pytestmark = pytest.mark.skip(reason="Scaffold only: implementation pending")


def test_frame_ids_strictly_increasing():
    """frame_id values are strictly increasing and never reused."""
    raise NotImplementedError("Test not written yet")


def test_timestamps_monotonic():
    """timestamp_s values are monotonic."""
    raise NotImplementedError("Test not written yet")


def test_match_by_frame_id():
    """Packets with identical frame_id are matched."""
    raise NotImplementedError("Test not written yet")


def test_mismatched_frame_id_rejected():
    """Packets with different frame_id are never paired."""
    raise NotImplementedError("Test not written yet")


def test_evicted_frame_lookup_returns_none():
    """Frame buffer lookup of an evicted frame_id returns None."""
    raise NotImplementedError("Test not written yet")
