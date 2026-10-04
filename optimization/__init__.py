"""Import-safe name for the 03_optimization owner directory; no duplicated code."""

from pathlib import Path

__path__ = [str(Path(__file__).resolve().parent.parent / "03_optimization")]
