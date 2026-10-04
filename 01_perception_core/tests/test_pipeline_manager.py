"""
Tests for pipeline orchestration (Module 01).

Implementation status:
    Scaffold only. Every test below is skipped until the component exists.
    Remove the module-level skip marker when implementing the tests.

Required test cases:
1. Modules execute in the order 02 -> 03 -> 04 -> 05 -> FSM.
2. A failing module is marked and the pipeline degrades without crashing.
3. Queue overflow follows the configured policy and drops are counted.
4. Graceful shutdown releases the camera and flushes logs.
5. Health monitor records measured per-module timing.
"""

import pytest

pytestmark = pytest.mark.skip(reason="Scaffold only: implementation pending")


def test_modules_run_in_documented_order():
    """Modules execute in the order 02 -> 03 -> 04 -> 05 -> FSM."""
    raise NotImplementedError("Test not written yet")


def test_failing_module_degrades_gracefully():
    """A failing module is marked and the pipeline degrades without crashing."""
    raise NotImplementedError("Test not written yet")


def test_queue_overflow_counted():
    """Queue overflow follows the configured policy and drops are counted."""
    raise NotImplementedError("Test not written yet")


def test_shutdown_releases_camera():
    """Graceful shutdown releases the camera and flushes logs."""
    raise NotImplementedError("Test not written yet")


def test_health_monitor_records_timing():
    """Health monitor records measured per-module timing."""
    raise NotImplementedError("Test not written yet")
