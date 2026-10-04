"""
Tests for motion features (Module 03, Teammate 4).

Implementation status:
    Scaffold only. Every test below is skipped until the component exists.
    Remove the module-level skip marker when implementing the tests.

Required test cases:
1. Velocity uses timestamp differences, not frame counts.
2. frame_id gaps are handled without producing velocity spikes.
3. Joint angle of a synthetic known configuration is computed correctly.
4. Motion direction is expressed relative to rack axes.
"""

import pytest

pytestmark = pytest.mark.skip(reason="Scaffold only: implementation pending")


def test_velocity_uses_timestamps():
    """Velocity uses timestamp differences, not frame counts."""
    raise NotImplementedError("Test not written yet")


def test_frame_gap_handled():
    """frame_id gaps are handled without producing velocity spikes."""
    raise NotImplementedError("Test not written yet")


def test_joint_angle_known_geometry():
    """Joint angle of a synthetic known configuration is computed correctly."""
    raise NotImplementedError("Test not written yet")


def test_direction_rack_relative():
    """Motion direction is expressed relative to rack axes."""
    raise NotImplementedError("Test not written yet")
