"""Standalone detector settings matching the SIH DetectorConfig field layout."""

import math
import re
from dataclasses import fields, replace
from numbers import Real
from pathlib import Path

import yaml
from yolo.core.contracts import ConfigurationError, DetectorConfig


def validate_detector_settings(config):
    """Detector-only rules matching the frozen SIH aggregate validation."""
    if config.backend not in {"ultralytics", "mock", "none"}:
        raise ConfigurationError("unsupported detector backend")
    for name in ("tracking", "cpu_fallback"):
        if type(getattr(config, name)) is not bool:
            raise ConfigurationError(f"detector.{name} must be boolean")
    if not isinstance(config.device, str) or not config.device.strip():
        raise ConfigurationError("detector.device must be a nonempty string")
    for name in ("confidence_threshold", "iou_threshold"):
        v = getattr(config, name)
        if (
            isinstance(v, bool)
            or not isinstance(v, (int, float))
            or not math.isfinite(v)
            or not 0 <= v <= 1
        ):
            raise ConfigurationError(f"{name} must be finite in [0,1]")
    if config.class_whitelist is not None and (
        not isinstance(config.class_whitelist, list)
        or any(type(v) is not int or v < 0 for v in config.class_whitelist)
    ):
        raise ConfigurationError("class_whitelist must be a list of nonnegative IDs")
    for name in ("model_path", "classes_path", "tracker_path"):
        v = getattr(config, name)
        if v is not None and (not isinstance(v, (str, Path)) or not str(v).strip()):
            raise ConfigurationError(f"{name} must be a nonempty local path")


def validate_config(config: DetectorConfig) -> DetectorConfig:
    """Snapshot validated settings; asset existence is checked at initialization."""
    if not isinstance(config, DetectorConfig):
        raise TypeError("Module 02 requires yolo.core.contracts.DetectorConfig")
    config = replace(
        config,
        class_whitelist=(
            list(config.class_whitelist)
            if isinstance(config.class_whitelist, list)
            else config.class_whitelist
        ),
    )
    # Only detector rules are needed outside the SIH aggregate configuration.
    validate_detector_settings(config)
    device = config.device.strip().lower()
    if device == "cuda":
        device = "0"
    elif device.startswith("cuda:"):
        device = device[5:]
    if device not in {"auto", "cpu", "mps"} and not re.fullmatch(r"[0-9]+", device):
        raise ConfigurationError(
            "device must be auto, cpu, mps, cuda, cuda:N or a single nonnegative CUDA index"
        )
    config.device = device
    for name in ("model_path", "classes_path", "tracker_path"):
        path = getattr(config, name)
        if path is not None:
            setattr(config, name, Path(path).resolve())
    return config


def validate_tracker(values: dict, confidence_threshold: float | None = None) -> None:
    """Validate the installed adapter's local tracker settings before inference."""
    for name in (
        "track_high_thresh",
        "track_low_thresh",
        "new_track_thresh",
        "match_thresh",
    ):
        value = values.get(name)
        if (
            isinstance(value, bool)
            or not isinstance(value, Real)
            or not math.isfinite(value)
            or not 0 <= float(value) <= 1
        ):
            raise ConfigurationError(f"tracker.{name} must be finite in [0,1]")
    if values["track_low_thresh"] > values["track_high_thresh"]:
        raise ConfigurationError("tracker low threshold must not exceed high threshold")
    if confidence_threshold is not None:
        for name in ("track_high_thresh", "new_track_thresh"):
            if values[name] > confidence_threshold:
                raise ConfigurationError(
                    f"tracker.{name} must not exceed detector.confidence_threshold "
                    "when tracking is enabled; otherwise accepted detections may "
                    "be excluded from new tracks"
                )
    if type(values.get("track_buffer")) is not int or values["track_buffer"] < 0:
        raise ConfigurationError("tracker.track_buffer must be a nonnegative integer")
    if type(values.get("fuse_score")) is not bool:
        raise ConfigurationError("tracker.fuse_score must be boolean")
    if values.get("tracker_type") == "botsort":
        if values.get("gmc_method") not in {
            "orb",
            "sift",
            "ecc",
            "sparseOptFlow",
            "none",
            None,
        }:
            raise ConfigurationError("unsupported local BoT-SORT gmc_method")
        if "gmc_method" not in values:
            raise ConfigurationError("BoT-SORT requires gmc_method (null disables it)")
        for name in ("proximity_thresh", "appearance_thresh"):
            value = values.get(name)
            if (
                isinstance(value, bool)
                or not isinstance(value, Real)
                or not math.isfinite(value)
                or not 0 <= float(value) <= 1
            ):
                raise ConfigurationError(f"tracker.{name} must be finite in [0,1]")


def load_config(path: str | Path) -> DetectorConfig:
    """Read detector-only YAML; paths are relative to its containing directory."""
    path = Path(path).resolve()
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as exc:
        raise ConfigurationError(
            f"cannot read YOLO configuration {path}: {exc}"
        ) from exc
    if (
        not isinstance(data, dict)
        or set(data) != {"detector"}
        or not isinstance(data["detector"], dict)
    ):
        raise ConfigurationError("YOLO YAML must contain a single detector mapping")
    values = dict(data["detector"])
    unknown = set(values) - {field.name for field in fields(DetectorConfig)}
    if unknown:
        raise ConfigurationError(f"unknown detector settings: {sorted(unknown)}")
    for name in ("model_path", "classes_path", "tracker_path"):
        value = values.get(name)
        if value is not None:
            if not isinstance(value, str) or not value.strip():
                raise ConfigurationError(f"{name} must be a nonempty local path")
            values[name] = path.parent / value
    return validate_config(DetectorConfig(**values))
