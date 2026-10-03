"""Utility helpers used across the project."""

from __future__ import annotations

from pathlib import Path


def ensure_directory(path: str | Path) -> Path:
    """Create a directory if it does not already exist."""
    directory = Path(path)
    directory.mkdir(parents=True, exist_ok=True)
    return directory


def safe_int(value, default: int) -> int:
    """Convert a value to an integer while keeping a safe default."""
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def format_chain_code_preview(codes: list[int], limit: int = 25) -> str:
    """Return a readable preview of a chain code."""
    if not codes:
        return "No chain code generated"
    preview = "".join(str(code) for code in codes[:limit])
    if len(codes) > limit:
        preview += "..."
    return preview


def format_direction_summary(frequencies: dict[int, int]) -> str:
    """Create user-friendly frequency text for display."""
    return "\n".join(f"Direction {direction}: {frequencies.get(direction, 0)}" for direction in range(8))
