"""Import-safe name for the 02_yolo owner directory; no duplicated code."""

from pathlib import Path

__path__ = [str(Path(__file__).resolve().parent.parent / "02_yolo")]
