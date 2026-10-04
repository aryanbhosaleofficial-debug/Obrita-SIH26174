"""
Tests for contact detection (Module 04).

Implementation status:
    Scaffold only. Every test below is skipped until the component exists.
    Remove the module-level skip marker when implementing the tests.

Required test cases:
1. Hand landmarks on the boundary produce contact evidence.
2. Hand far from the boundary produces no contact.
3. Contact detector returns evidence only, never a procedure decision.
"""

import pytest

pytestmark = pytest.mark.skip(reason="Scaffold only: implementation pending")


def test_hand_on_boundary_contact():
    """Hand landmarks on the boundary produce contact evidence."""
    raise NotImplementedError("Test not written yet")


def test_hand_far_no_contact():
    """Hand far from the boundary produces no contact."""
    raise NotImplementedError("Test not written yet")


def test_contact_is_evidence_only():
    """Contact detector returns evidence only, never a procedure decision."""
    raise NotImplementedError("Test not written yet")
