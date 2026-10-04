"""Import-safe name for the 04_boundary owner directory; no duplicated code."""

from pathlib import Path

__path__ = [str(Path(__file__).resolve().parent.parent / "04_boundary")]
