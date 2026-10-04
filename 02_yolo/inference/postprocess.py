"""SIH compatibility facade over the unchanged coordinate/parser math."""

from yolo.adapters.sih import SIH_TYPES
from yolo.core.postprocess import BackendOutputError

__all__ = ["BackendOutputError", "clamp_source_box", "parse_results"]
from yolo.core.postprocess import clamp_source_box as core_clamp
from yolo.core.postprocess import parse_results as core_parse


def clamp_source_box(box, width, height):
    return core_clamp(box, width, height, types=SIH_TYPES)


def parse_results(results, shape, names, tracking):
    return core_parse(results, shape, names, tracking, types=SIH_TYPES)
