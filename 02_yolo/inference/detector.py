"""SIH compatibility facade; detector implementation lives in core.detector."""

from importlib.util import find_spec

from yolo.adapters.sih import SIH_TYPES, adapt_config
from yolo.config import validate_config
from yolo.core.detector import NullDetector, ObjectDetector

from shared.errors import InitializationError

__all__ = [
    "InitializationError",
    "NullDetector",
    "ObjectDetector",
    "UltralyticsYoloDetector",
    "filter_detections",
]
from yolo.core.detector import UltralyticsYoloDetector as CoreDetector
from yolo.core.detector import filter_detections as core_filter


class UltralyticsYoloDetector(CoreDetector):
    def __init__(self, config):
        super().__init__(adapt_config(validate_config(config)), types=SIH_TYPES)

    def _find_spec(self, name):
        return find_spec(name)


def filter_detections(detections, shape, config, diagnostics=None):
    return core_filter(detections, shape, config, diagnostics, types=SIH_TYPES)
