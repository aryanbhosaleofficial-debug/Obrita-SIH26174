"""
Tests for ObjectFrame assembly (Module 02).

Implementation status:
    Scaffold only. Every test below is skipped until the component exists.
    Remove the module-level skip marker when implementing the tests.

Required test cases:
1. frame_id and timestamp_s are copied unchanged from FramePacket.
2. All boxes lie within original source-frame bounds.
3. Output is an instance of shared.schemas.object_frame.ObjectFrame.
4. Missing reference anchor gives an empty anchor list, not a fabricated one.
5. is_stable is set only after multi-frame confirmation.
"""

import pytest

pytestmark = pytest.mark.skip(reason="Scaffold only: implementation pending")


def test_frame_metadata_copied_unchanged():
    """frame_id and timestamp_s are copied unchanged from FramePacket."""
    raise NotImplementedError("Test not written yet")


def test_coordinates_in_original_frame():
    """All boxes lie within original source-frame bounds."""
    raise NotImplementedError("Test not written yet")


def test_uses_shared_schema():
    """Output is an instance of shared.schemas.object_frame.ObjectFrame."""
    raise NotImplementedError("Test not written yet")


def test_missing_anchor_reported():
    """Missing reference anchor gives an empty anchor list, not a fabricated one."""
    raise NotImplementedError("Test not written yet")


def test_stability_flag_after_confirmation():
    """is_stable is set only after multi-frame confirmation."""
    raise NotImplementedError("Test not written yet")
