"""Tests for the Module 04 chain-code helpers."""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


def _load_module(name: str, relative_path: str):
    path = ROOT / relative_path
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec is not None and spec.loader is not None
    spec.loader.exec_module(module)
    return module


chain_histogram = _load_module(
    "chain_histogram", "chain_code/chain_histogram.py"
).chain_histogram
normalize_chain_code = _load_module(
    "chain_normalizer", "chain_code/chain_normalizer.py"
).normalize_chain_code
differential_chain_code = _load_module(
    "differential_chain", "chain_code/differential_chain.py"
).differential_chain_code
freeman_chain = _load_module(
    "freeman_chain", "chain_code/freeman_chain.py"
).freeman_chain


def _square_contour_clockwise():
    """Simple square contour (clockwise, origin at top-left)."""
    return [
        (0.0, 0.0),
        (1.0, 0.0),
        (2.0, 0.0),
        (2.0, 1.0),
        (2.0, 2.0),
        (1.0, 2.0),
        (0.0, 2.0),
        (0.0, 1.0),
        (0.0, 0.0),
    ]


def test_freeman_square():
    """Freeman chain code of a synthetic square matches the expected sequence."""
    contour = _square_contour_clockwise()
    # The recovered source omitted the closing edge. A closed square has eight
    # unit transitions, including the final northward transition.
    expected = [0, 0, 2, 2, 4, 4, 6, 6]
    assert freeman_chain(contour) == expected


def test_start_point_normalization():
    """Shifted start points normalize to the same chain."""
    contour = _square_contour_clockwise()
    shifted = contour[3:] + contour[:3]
    assert normalize_chain_code(freeman_chain(contour)) == normalize_chain_code(
        freeman_chain(shifted)
    )


def test_differential_rotation_invariance():
    """Differential code is unchanged under 90-degree rotation."""
    contour = _square_contour_clockwise()
    chain = freeman_chain(contour)
    normalized = normalize_chain_code(chain)
    diff = differential_chain_code(normalized)

    rotated = [((code + 2) % 8) for code in chain]
    rotated_normalized = normalize_chain_code(rotated)
    rotated_diff = differential_chain_code(rotated_normalized)

    assert diff == rotated_diff


def test_histogram_normalized():
    """Chain histogram sums to 1."""
    hist = chain_histogram([0, 0, 1, 2, 2, 7])
    assert sum(hist) == pytest.approx(1.0)
    assert len(hist) == 8
