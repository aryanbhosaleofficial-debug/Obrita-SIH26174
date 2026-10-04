"""SIH configuration facade over the canonical Module 02 detector settings.

The wrappers preserve shared configuration/exception contracts. YAML parsing,
thresholds, paths and tracker validation have one implementation in core.config.
"""

from dataclasses import asdict
from pathlib import Path

from yolo.adapters.sih import adapt_config
from yolo.core import config as core_config
from yolo.core.contracts import ConfigurationError as CoreConfigurationError

from shared.config import ConfigurationError, DetectorConfig


def validate_config(config: DetectorConfig) -> DetectorConfig:
    internal = adapt_config(config)
    try:
        snapshot = core_config.validate_config(internal)
    except CoreConfigurationError as exc:
        raise ConfigurationError(str(exc)) from exc
    return DetectorConfig(**asdict(snapshot))


def load_config(path: str | Path) -> DetectorConfig:
    try:
        snapshot = core_config.load_config(path)
    except CoreConfigurationError as exc:
        raise ConfigurationError(str(exc)) from exc
    return DetectorConfig(**asdict(snapshot))


def validate_tracker(values: dict, confidence_threshold: float | None = None) -> None:
    try:
        core_config.validate_tracker(values, confidence_threshold)
    except CoreConfigurationError as exc:
        raise ConfigurationError(str(exc)) from exc
