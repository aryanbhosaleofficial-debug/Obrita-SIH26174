"""Preserved SIH entry point: PreparedFrame -> unchanged shared ObjectFrame."""

from yolo.adapters.sih import SIH_TYPES, adapt_config, adapt_prepared
from yolo.config import load_config, validate_config
from yolo.core.pipeline import DetectorPipeline
from yolo.inference.detector import UltralyticsYoloDetector

from shared.config import ConfigurationError


class YoloPipeline(DetectorPipeline):
    def __init__(self, config, detector=None, *, semantic_config=None, verifier=None):
        config = validate_config(config)
        if detector is None and config.backend == "mock":
            raise ConfigurationError(
                "mock backend requires an explicitly injected detector"
            )
        if detector is None and config.backend == "ultralytics":
            detector = UltralyticsYoloDetector(config)
        super().__init__(
            adapt_config(config),
            detector,
            types=SIH_TYPES,
            semantic_config=semantic_config,
            verifier=verifier,
        )
        self.config = config

    @classmethod
    def from_yaml(cls, path, detector=None):
        return cls(load_config(path), detector)

    def process(self, prepared):
        return super().process(adapt_prepared(prepared))
