"""Load temporal settings from the existing Module 03 owner configuration."""

from pathlib import Path

from integration.configuration import parse, read
from shared.config import ConfigurationError, StabilizationConfig

OptimizationConfig = StabilizationConfig  # One authoritative config definition.


def load_config(path: str | Path) -> StabilizationConfig:
    data = read(Path(path))
    allowed = {
        "stabilization",
        "hand_tracker",
        "reference_frame",
        "interaction",
        "debug",
    }
    if set(data) - allowed:
        raise ConfigurationError("unknown optimization configuration section")
    config = parse(StabilizationConfig, data.get("stabilization", {}))
    config.validate()
    return config
