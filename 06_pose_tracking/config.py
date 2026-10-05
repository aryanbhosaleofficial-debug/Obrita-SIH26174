"""Module 06 configuration. Paths in YAML resolve relative to the YAML file."""

from __future__ import annotations

import math
from dataclasses import dataclass, fields, replace
from numbers import Real
from pathlib import Path

import yaml

from shared.config import ConfigurationError

MODULE_ROOT = Path(__file__).resolve().parent
DEFAULT_CONFIG_PATH = MODULE_ROOT / "config" / "pose_tracking.yaml"


@dataclass(frozen=True)
class PoseTrackingConfig:
    body_enabled: bool = True
    hands_enabled: bool = True
    pose_model_path: Path | None = None
    hand_model_path: Path | None = None
    max_hands: int = 2
    min_pose_detection_confidence: float = 0.5
    min_pose_presence_confidence: float = 0.5
    min_hand_detection_confidence: float = 0.5
    min_hand_presence_confidence: float = 0.5
    min_tracking_confidence: float = 0.5
    input_mirrored: bool = False
    # True when frames are horizontally flipped (selfie view) BEFORE inference.
    swap_handedness: bool | None = None
    # None = MediaPipe convention: its hand labels assume mirrored input, so they
    # are swapped when input_mirrored is False. Set explicitly to override.
    smoothing_alpha: float = 0.7
    # EMA weight of the newest observation; 1.0 disables extra smoothing.
    max_hold_frames: int = 2
    # Frames a lost body/hand is re-published as held (observed=False); 0 disables.
    jump_reset_fraction: float = 0.15
    # Wrist/hip jump (fraction of image diagonal) that restarts smoothing instead of blending.
    max_time_gap_s: float = 1.0
    # Longer timestamp gaps clear smoothing/hold state.

    @property
    def effective_swap_handedness(self) -> bool:
        return (
            (not self.input_mirrored)
            if self.swap_handedness is None
            else self.swap_handedness
        )

    def validate(self) -> PoseTrackingConfig:
        for name in ("body_enabled", "hands_enabled", "input_mirrored"):
            if type(getattr(self, name)) is not bool:
                raise ConfigurationError(f"{name} must be boolean")
        if self.swap_handedness is not None and type(self.swap_handedness) is not bool:
            raise ConfigurationError("swap_handedness must be boolean or null")
        if not self.body_enabled and not self.hands_enabled:
            raise ConfigurationError("enable at least one of body or hands")
        if type(self.max_hands) is not int or not 1 <= self.max_hands <= 4:
            raise ConfigurationError("max_hands must be an integer in [1, 4]")
        if type(self.max_hold_frames) is not int or not 0 <= self.max_hold_frames <= 30:
            raise ConfigurationError("max_hold_frames must be an integer in [0, 30]")
        for name in (
            "min_pose_detection_confidence",
            "min_pose_presence_confidence",
            "min_hand_detection_confidence",
            "min_hand_presence_confidence",
            "min_tracking_confidence",
        ):
            value = getattr(self, name)
            if not _real(value) or not 0.0 <= value <= 1.0:
                raise ConfigurationError(f"{name} must be in [0, 1]")
        for name in ("smoothing_alpha", "jump_reset_fraction"):
            value = getattr(self, name)
            if not _real(value) or not 0.0 < value <= 1.0:
                raise ConfigurationError(f"{name} must be in (0, 1]")
        if not _real(self.max_time_gap_s) or self.max_time_gap_s <= 0:
            raise ConfigurationError("max_time_gap_s must be finite and positive")
        for name, enabled in (
            ("pose_model_path", self.body_enabled),
            ("hand_model_path", self.hands_enabled),
        ):
            path = getattr(self, name)
            if enabled and path is None:
                raise ConfigurationError(
                    f"{name} is required when that model is enabled"
                )
            if path is not None and not isinstance(path, Path):
                raise ConfigurationError(f"{name} must be a Path")
        return self


def _real(value) -> bool:
    return (
        isinstance(value, Real) and not isinstance(value, bool) and math.isfinite(value)
    )


def load_config(
    path: str | Path = DEFAULT_CONFIG_PATH, **overrides
) -> PoseTrackingConfig:
    """Load ``pose_tracking:`` from YAML. Unknown keys are rejected, not ignored."""
    path = Path(path)
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as exc:
        raise ConfigurationError(
            f"cannot read pose tracking config {path}: {exc}"
        ) from exc
    if not isinstance(data, dict) or set(data) != {"pose_tracking"}:
        raise ConfigurationError("expected a single top-level 'pose_tracking' mapping")
    section = data["pose_tracking"]
    if not isinstance(section, dict):
        raise ConfigurationError("'pose_tracking' must be a mapping")
    known = {f.name for f in fields(PoseTrackingConfig)}
    unknown = set(section) - known
    if unknown:
        raise ConfigurationError(f"unknown pose_tracking keys: {sorted(unknown)}")
    values = dict(section)
    for key in ("pose_model_path", "hand_model_path"):
        if values.get(key) is not None:
            if not isinstance(values[key], str):
                raise ConfigurationError(f"{key} must be a path string")
            values[key] = (path.parent / values[key]).resolve()
    config = replace(PoseTrackingConfig(**values), **overrides)
    return config.validate()
