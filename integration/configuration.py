"""Load owner configs once. Profiles contain paths, never duplicate thresholds."""

from dataclasses import fields
from pathlib import Path

import yaml

from shared.config import (
    ConfigurationError,
    DebugConfig,
    DetectorConfig,
    DistanceThresholds,
    HandTrackerConfig,
    InteractionConfig,
    PipelineConfig,
    PreprocessingConfig,
    ReferenceFrameConfig,
    StabilizationConfig,
)


def read(path: Path):
    try:
        value = yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        raise ConfigurationError(str(exc)) from exc
    if not isinstance(value, dict):
        raise ConfigurationError(f"expected mapping in {path}")
    return value


def parse(cls, values):
    if not isinstance(values, dict) or set(values) - {f.name for f in fields(cls)}:
        raise ConfigurationError(f"unknown or invalid {cls.__name__} settings")
    try:
        return cls(**values)
    except TypeError as exc:
        raise ConfigurationError(str(exc)) from exc


def load_profile(path: Path) -> PipelineConfig:
    profile = read(path)["pipeline"]
    if not isinstance(profile, dict) or set(profile) != {
        "core",
        "yolo",
        "optimization",
    }:
        raise ConfigurationError(
            "pipeline profile must reference core, yolo and optimization files"
        )
    paths = {}
    for key, value in profile.items():
        if not isinstance(value, str) or not value:
            raise ConfigurationError("profile paths must be nonempty strings")
        paths[key] = (path.parent / value).resolve()
    core = read(paths["core"])
    if (
        set(core) != {"perception"}
        or not isinstance(core["perception"], dict)
        or set(core["perception"]) - {"preprocessing"}
    ):
        raise ConfigurationError("core configuration owns preprocessing only")
    yolo = read(paths["yolo"])
    if set(yolo) != {"detector"}:
        raise ConfigurationError("YOLO configuration requires detector section")
    opt = read(paths["optimization"])
    expected = {
        "hand_tracker",
        "reference_frame",
        "interaction",
        "stabilization",
        "debug",
    }
    if set(opt) - expected:
        raise ConfigurationError("unknown optimization configuration section")
    config = PipelineConfig(
        preprocessing=parse(
            PreprocessingConfig, core["perception"].get("preprocessing", {})
        ),
        detector=parse(DetectorConfig, yolo["detector"]),
    )
    for name, cls in (
        ("hand_tracker", HandTrackerConfig),
        ("reference_frame", ReferenceFrameConfig),
        ("interaction", InteractionConfig),
        ("stabilization", StabilizationConfig),
        ("debug", DebugConfig),
    ):
        values = opt.get(name, {})
        if not isinstance(values, dict):
            raise ConfigurationError(f"{name} must be a mapping")
        values = dict(values)
        if name == "interaction":
            for key in ("rack_relative", "image_diagonal"):
                if key in values:
                    values[key] = parse(DistanceThresholds, values[key])
        setattr(config, name, parse(cls, values))
    config.validate()
    for obj, field, owner in (
        (config.detector, "model_path", "yolo"),
        (config.detector, "tracker_path", "yolo"),
        (config.detector, "classes_path", "yolo"),
        (config.hand_tracker, "model_path", "optimization"),
    ):
        value = getattr(obj, field)
        if value is not None:
            setattr(obj, field, (paths[owner].parent / value).resolve())
    return config
