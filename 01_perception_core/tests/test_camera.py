"""
Tests for camera capture (Module 01).

Implementation status:
    Scaffold only. Every test below is skipped until the component exists.
    Remove the module-level skip marker when implementing the tests.

Required test cases:
1. Camera config with a null source is rejected with a clear error.
2. Frame reader works on a local video file without a physical camera.
3. Actual (driver-accepted) resolution/FPS are read back and reported.
4. A failed read produces an error ModuleStatus instead of crashing.
5. Captured frame shape/dtype are preserved in the FramePacket.
"""

import pytest

pytestmark = pytest.mark.skip(reason="Scaffold only: implementation pending")


def test_config_rejects_missing_source():
    """Camera config with a null source is rejected with a clear error."""
    raise NotImplementedError("Test not written yet")


def test_reads_recorded_video_offline():
    """Frame reader works on a local video file without a physical camera."""
    raise NotImplementedError("Test not written yet")


def test_reports_actual_resolution_and_fps():
    """Actual (driver-accepted) resolution/FPS are read back and reported."""
    raise NotImplementedError("Test not written yet")


def test_read_failure_sets_error_status():
    """A failed read produces an error ModuleStatus instead of crashing."""
    raise NotImplementedError("Test not written yet")


def test_source_frame_not_modified():
    """Captured frame shape/dtype are preserved in the FramePacket."""
    raise NotImplementedError("Test not written yet")
