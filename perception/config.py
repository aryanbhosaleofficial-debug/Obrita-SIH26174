"""Strict YAML configuration; paths resolve relative to the YAML file."""

from __future__ import annotations

import math
from dataclasses import dataclass, field, fields
from pathlib import Path
from typing import Any

import yaml


class ConfigurationError(ValueError):
    """An unsafe or unsupported perception setting."""


@dataclass
class PreprocessingConfig:
    max_width: int | None = None
    equalize_luminance: bool = False


@dataclass
class DetectorConfig:
    backend: str = "ultralytics"
    model_path: Path | None = None
    confidence_threshold: float = 0.5
    iou_threshold: float = 0.45
    class_whitelist: list[int] | None = None
    device: str = "auto"
    cpu_fallback: bool = True
    tracking: bool = False
    tracker_path: Path | None = None
    # Local tracker YAML, with any appearance/ReID downloads disabled.


@dataclass
class HandTrackerConfig:
    enabled: bool = True
    backend: str = "mediapipe"
    model_path: Path | None = None
    max_hands: int = 2
    min_detection_confidence: float = 0.5
    min_presence_confidence: float = 0.5
    min_tracking_confidence: float = 0.5


@dataclass
class ReferenceFrameConfig:
    enabled: bool = False
    type: str = "manual"
    reference_id: str = "rack"
    corners_normalized: list[list[float]] | None = None
    # Physical board order: origin, +x, +x/+y, +y; NOT sorted by image direction.


@dataclass
class InteractionConfig:
    proximity_threshold: float = 0.08
    contact_threshold: float = 0.03
    ambiguity_margin: float = 0.01
    trend_threshold: float = 0.005
    motion_speed_threshold: float = 0.02


@dataclass
class StabilizationConfig:
    detection_min_frames: int = 3
    interaction_min_frames: int = 4
    max_missing_frames: int = 2
    ema_alpha: float = 0.5
    matching_iou_threshold: float = 0.3
    hand_matching_distance: float = 0.1
    max_time_gap_s: float = 1.0


@dataclass
class DebugConfig:
    draw_detections: bool = True
    draw_hands: bool = True
    draw_reference_axes: bool = True
    draw_associations: bool = True
    draw_warnings: bool = True


@dataclass
class PerceptionConfig:
    preprocessing: PreprocessingConfig = field(default_factory=PreprocessingConfig)
    detector: DetectorConfig = field(default_factory=DetectorConfig)
    hand_tracker: HandTrackerConfig = field(default_factory=HandTrackerConfig)
    reference_frame: ReferenceFrameConfig = field(default_factory=ReferenceFrameConfig)
    interaction: InteractionConfig = field(default_factory=InteractionConfig)
    stabilization: StabilizationConfig = field(default_factory=StabilizationConfig)
    debug: DebugConfig = field(default_factory=DebugConfig)

    def validate(self) -> None:
        """Validate also when a caller constructs dataclasses directly."""

        def number(
            name: str, value: Any, low: float, high: float, positive: bool = False
        ) -> None:
            if (
                isinstance(value, bool)
                or not isinstance(value, (float, int))
                or not math.isfinite(value)
                or not low <= value <= high
                or (positive and value <= 0)
            ):
                raise ConfigurationError(f"{name} must be finite in [{low}, {high}]")

        def integer(name: str, value: Any, low: int) -> None:
            if type(value) is not int or value < low:
                raise ConfigurationError(f"{name} must be an integer >= {low}")

        for section in fields(self):
            obj = getattr(self, section.name)
            for item in fields(obj):
                if (
                    item.type in (bool, "bool")
                    and type(getattr(obj, item.name)) is not bool
                ):
                    raise ConfigurationError(
                        f"{section.name}.{item.name} must be boolean"
                    )
        d, h, r, i, s = (
            self.detector,
            self.hand_tracker,
            self.reference_frame,
            self.interaction,
            self.stabilization,
        )
        if d.backend not in ("ultralytics", "mock", "none"):
            raise ConfigurationError("unsupported detector backend")
        if h.backend not in ("mediapipe", "mock", "none"):
            raise ConfigurationError("unsupported hand tracker backend")
        if not isinstance(d.device, str) or not d.device.strip():
            raise ConfigurationError("detector.device must be a nonempty string")
        if r.type != "manual":
            raise ConfigurationError(
                "built-in reference type must be manual; inject another transformer"
            )
        if not isinstance(r.reference_id, str) or not r.reference_id:
            raise ConfigurationError("reference_id must be nonempty")
        for name, value in (
            ("confidence_threshold", d.confidence_threshold),
            ("iou_threshold", d.iou_threshold),
            ("min_detection_confidence", h.min_detection_confidence),
            ("min_presence_confidence", h.min_presence_confidence),
            ("min_tracking_confidence", h.min_tracking_confidence),
            ("matching_iou_threshold", s.matching_iou_threshold),
        ):
            number(name, value, 0, 1)
        number("ema_alpha", s.ema_alpha, 0, 1, True)
        for name in (
            "proximity_threshold",
            "contact_threshold",
            "ambiguity_margin",
            "trend_threshold",
            "motion_speed_threshold",
        ):
            number(
                name, getattr(i, name), 0, float("inf"), name == "proximity_threshold"
            )
        if i.contact_threshold > i.proximity_threshold:
            raise ConfigurationError(
                "contact_threshold must not exceed proximity_threshold"
            )
        number("hand_matching_distance", s.hand_matching_distance, 0, 1, True)
        number("max_time_gap_s", s.max_time_gap_s, 0, float("inf"), True)
        for name in ("detection_min_frames", "interaction_min_frames"):
            integer(name, getattr(s, name), 1)
        integer("max_missing_frames", s.max_missing_frames, 0)
        integer("max_hands", h.max_hands, 1)
        if self.preprocessing.max_width is not None:
            integer("max_width", self.preprocessing.max_width, 1)
        if d.class_whitelist is not None:
            if not isinstance(d.class_whitelist, list):
                raise ConfigurationError("class_whitelist must be a list")
            for value in d.class_whitelist:
                integer("class_whitelist item", value, 0)
        for obj, name in ((d, "model_path"), (d, "tracker_path"), (h, "model_path")):
            value = getattr(obj, name)
            if value is not None:
                if not isinstance(value, (str, Path)) or not str(value).strip():
                    raise ConfigurationError(f"{name} must be a nonempty local path")
                setattr(obj, name, Path(value))
        if r.enabled and r.corners_normalized is None:
            raise ConfigurationError(
                "enabled manual reference requires corners_normalized"
            )
        if r.corners_normalized is not None:
            from perception.coordinate_frame import validate_corners

            validate_corners(r.corners_normalized)

    @classmethod
    def from_yaml(cls, path: str | Path) -> PerceptionConfig:
        path = Path(path).resolve()
        with path.open(encoding="utf-8") as stream:
            try:
                data = yaml.safe_load(stream)
            except yaml.YAMLError as exc:
                raise ConfigurationError(f"Invalid YAML in {path}: {exc}") from exc
        if (
            not isinstance(data, dict)
            or set(data) != {"perception"}
            or not isinstance(data["perception"], dict)
        ):
            raise ConfigurationError("YAML must contain a single perception mapping")
        config = cls()
        sections = {f.name for f in fields(config)}
        for name, values in data["perception"].items():
            if name not in sections or not isinstance(values, dict):
                raise ConfigurationError(f"unknown section or invalid mapping: {name}")
            section_type = type(getattr(config, name))
            unknown = set(values) - {f.name for f in fields(section_type)}
            if unknown:
                raise ConfigurationError(f"unknown {name} settings: {sorted(unknown)}")
            setattr(config, name, section_type(**values))
        config.validate()
        for obj, name in (
            (config.detector, "model_path"),
            (config.detector, "tracker_path"),
            (config.hand_tracker, "model_path"),
        ):
            value = getattr(obj, name)
            if value is not None:
                setattr(obj, name, (path.parent / value).resolve())
        return config
