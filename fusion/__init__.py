"""Import-safe locator for Module 05; no duplicated implementation."""
from pathlib import Path

__path__ = [str(Path(__file__).resolve().parent.parent / "05_perception_fusion")]


def __getattr__(name):
    if name == "FusionPipeline":
        from fusion.pipeline import FusionPipeline

        return FusionPipeline
    raise AttributeError(name)
