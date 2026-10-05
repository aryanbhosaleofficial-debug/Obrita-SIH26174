"""Import-safe locator for Module 03's optional local landmark helper."""
from pathlib import Path

__path__ = [str(Path(__file__).resolve().parent.parent / "06_pose_tracking")]


def __getattr__(name):
    from importlib import import_module

    return getattr(import_module("06_pose_tracking"), name)
