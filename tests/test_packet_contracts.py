"""
Shared packet contract tests.

These tests check the shared contracts that already exist in the scaffold
(shared/schemas, shared/enums) and repository-wide contract rules.
They do not test any perception algorithm.

Run from the repository root:
    python -m pytest

Checks:
1. Every packet schema is a dataclass with frame_id and timestamp_s.
2. Every packet schema carries a ModuleStatus field.
3. Packets consumed by Perception Fusion / Procedure FSM carry target_track_id.
4. BoundaryState contains the states Module 04 must be able to report.
5. Packet classes are defined only in shared/schemas (no duplicate definitions in modules).
6. No Python file imports a numbered module directory with a normal import statement.
"""

import dataclasses
import re
from pathlib import Path

import pytest

from shared.enums import BoundaryState, ModuleStatus
from shared.schemas import (
    ActivityEvent,
    BoundaryOutputPacket,
    FramePacket,
    ObjectFrame,
    OptimizationOutputPacket,
    SpatialFeaturePacket,
)

REPO_ROOT = Path(__file__).resolve().parents[1]

PACKETS = [
    FramePacket,
    ObjectFrame,
    SpatialFeaturePacket,
    OptimizationOutputPacket,
    BoundaryOutputPacket,
    ActivityEvent,
]


def _field_names(cls) -> set[str]:
    return {f.name for f in dataclasses.fields(cls)}


def _python_files(skip_shared: bool):
    skipped = {".venv", "venv"} | ({"shared"} if skip_shared else set())
    for path in REPO_ROOT.rglob("*.py"):
        rel = path.relative_to(REPO_ROOT)
        if rel.parts[0] in skipped:
            continue
        yield rel, path.read_text(encoding="utf-8")


@pytest.mark.parametrize("packet", PACKETS, ids=lambda c: c.__name__)
def test_packet_has_frame_id_and_timestamp(packet):
    assert dataclasses.is_dataclass(packet)
    assert {"frame_id", "timestamp_s"} <= _field_names(packet)


@pytest.mark.parametrize("packet", PACKETS, ids=lambda c: c.__name__)
def test_packet_has_module_status(packet):
    status = next(f for f in dataclasses.fields(packet) if f.name == "status")
    assert status.default is ModuleStatus.OK


@pytest.mark.parametrize(
    "packet",
    [SpatialFeaturePacket, OptimizationOutputPacket, BoundaryOutputPacket, ActivityEvent],
    ids=lambda c: c.__name__,
)
def test_downstream_packets_carry_target_track_id(packet):
    assert "target_track_id" in _field_names(packet)


def test_boundary_state_covers_required_states():
    required = {"stationary", "moving", "rotating", "contact", "separating"}
    assert required <= {state.value for state in BoundaryState}


@pytest.mark.parametrize("packet", PACKETS, ids=lambda c: c.__name__)
def test_packet_not_redefined_outside_shared(packet):
    pattern = re.compile(rf"^\s*class\s+{packet.__name__}\b", re.MULTILINE)
    offenders = [str(rel) for rel, text in _python_files(skip_shared=True) if pattern.search(text)]
    assert offenders == []


def test_no_numbered_module_imports():
    pattern = re.compile(r"^\s*(from|import)\s+0\d_", re.MULTILINE)
    offenders = [str(rel) for rel, text in _python_files(skip_shared=False) if pattern.search(text)]
    assert offenders == []
