"""Validated effective settings; the existing YAML file is never overwritten."""

import math
from dataclasses import dataclass, field
from pathlib import Path

import yaml


class BoundaryConfigurationError(ValueError):
    pass


@dataclass
class BoundaryConfig:
    roi_padding: int = 0
    padding_ratio: float = 0.1
    blur_kernel: int = 3
    segmentation_method: str = "threshold"
    segmentation_params: dict = field(default_factory=dict)
    open_kernel: int = 0
    close_kernel: int = 0
    iterations: int = 1
    min_component_area: int = 0
    min_area: float = 20.0
    max_area: float | None = None
    min_perimeter: float = 0.0
    contact_distance_px: float = 20.0
    history_frames: int = 20
    max_missing_frames: int = 2
    max_time_gap_s: float = 1.0
    normalize_start_point: bool = True
    use_differential: bool = True
    require_optimization_quality: bool = True
    require_valid_rack_reference: bool = False
    min_confidence: float = 0.35
    min_roi_stddev: float = 5.0
    min_foreground_fraction: float = 0.01
    max_foreground_fraction: float = 0.90
    min_component_dominance: float = 0.80
    min_contour_fill_fraction: float = 0.85
    min_separability: float = 0.80
    border_margin_px: int = 1
    max_border_sides: int = 2
    max_border_point_fraction: float = 0.35
    motion_min_frames: int = 3
    stationary_tolerance_px: float = 1.0
    moving_threshold_px: float = 2.0
    separation_distance_increase_px: float = 2.0
    contact_min_confidence: float = 0.5
    confirmation_n: int = 2
    confirmation_m: int = 3
    min_motion_coherence: float = 0.8

    def validate(self):
        for name in (
            "roi_padding",
            "blur_kernel",
            "open_kernel",
            "close_kernel",
            "iterations",
            "min_component_area",
            "history_frames",
            "max_missing_frames",
            "border_margin_px",
            "max_border_sides",
            "motion_min_frames",
            "confirmation_n",
            "confirmation_m",
        ):
            value = getattr(self, name)
            minimum = (
                1
                if name
                in ("iterations", "history_frames", "confirmation_n", "confirmation_m")
                else 0
            )
            if type(value) is not int or value < minimum:
                raise BoundaryConfigurationError(
                    f"{name} must be an integer >= {minimum}"
                )
        if self.blur_kernel not in (0, 1) and self.blur_kernel % 2 == 0:
            raise BoundaryConfigurationError("blur_kernel must be odd or 0")
        if not 1 <= self.max_border_sides <= 3:
            raise BoundaryConfigurationError("max_border_sides must be in [1, 3]")
        if not 3 <= self.motion_min_frames <= self.history_frames:
            raise BoundaryConfigurationError(
                "motion_min_frames must be in [3, history_frames]"
            )
        if not self.confirmation_n <= self.confirmation_m <= self.history_frames:
            raise BoundaryConfigurationError(
                "confirmation_n <= confirmation_m <= history_frames required"
            )
        for name in (
            "padding_ratio",
            "min_area",
            "min_perimeter",
            "contact_distance_px",
            "max_time_gap_s",
            "min_confidence",
            "min_roi_stddev",
            "stationary_tolerance_px",
            "moving_threshold_px",
            "separation_distance_increase_px",
            "min_foreground_fraction",
            "max_foreground_fraction",
            "min_component_dominance",
            "min_contour_fill_fraction",
            "min_separability",
            "max_border_point_fraction",
            "contact_min_confidence",
            "min_motion_coherence",
        ):
            value = getattr(self, name)
            if (
                isinstance(value, bool)
                or not isinstance(value, (int, float))
                or not math.isfinite(value)
                or value < 0
            ):
                raise BoundaryConfigurationError(
                    f"{name} must be finite and nonnegative"
                )
        if (
            self.contact_distance_px == 0
            or self.max_time_gap_s == 0
            or self.min_confidence > 1
        ):
            raise BoundaryConfigurationError(
                "invalid contact/time/confidence threshold"
            )
        if (
            self.min_roi_stddev <= 0
            or not 0 < self.min_foreground_fraction < self.max_foreground_fraction < 1
        ):
            raise BoundaryConfigurationError(
                "ROI information must be positive and 0 < min/max foreground fraction < 1"
            )
        for name in (
            "min_component_dominance",
            "min_contour_fill_fraction",
            "min_separability",
            "max_border_point_fraction",
            "contact_min_confidence",
            "min_motion_coherence",
        ):
            if not 0 < getattr(self, name) <= 1:
                raise BoundaryConfigurationError(f"{name} must be in (0, 1]")
        if (
            self.moving_threshold_px <= self.stationary_tolerance_px
            or self.separation_distance_increase_px <= 0
        ):
            raise BoundaryConfigurationError(
                "moving threshold must exceed stationary tolerance; separation increase must be positive"
            )
        if self.max_area is not None and (
            isinstance(self.max_area, bool)
            or not isinstance(self.max_area, (int, float))
            or not math.isfinite(self.max_area)
            or self.max_area < self.min_area
        ):
            raise BoundaryConfigurationError("max_area must be finite and >= min_area")
        for name in (
            "normalize_start_point",
            "use_differential",
            "require_optimization_quality",
            "require_valid_rack_reference",
        ):
            if type(getattr(self, name)) is not bool:
                raise BoundaryConfigurationError(f"{name} must be boolean")
        if self.segmentation_method not in (
            "threshold",
            "canny",
            "adaptive",
            "adaptive_threshold",
        ):
            raise BoundaryConfigurationError(
                "supported segmentation: threshold, canny, adaptive"
            )
        if not isinstance(self.segmentation_params, dict):
            raise BoundaryConfigurationError("segmentation_params must be a mapping")
        allowed = (
            {"threshold", "invert"}
            if self.segmentation_method == "threshold"
            else (
                {"low", "high"}
                if self.segmentation_method == "canny"
                else {"block_size", "c"}
            )
        )
        if set(self.segmentation_params) - allowed:
            raise BoundaryConfigurationError("unknown segmentation parameters")
        for name, value in self.segmentation_params.items():
            if name == "invert":
                if type(value) is not bool:
                    raise BoundaryConfigurationError("invert must be boolean")
            elif (
                isinstance(value, bool)
                or not isinstance(value, (int, float))
                or not math.isfinite(value)
            ):
                raise BoundaryConfigurationError(f"segmentation {name} must be finite")
            elif name in ("threshold", "low", "high") and not 0 <= value <= 255:
                raise BoundaryConfigurationError(
                    f"segmentation {name} must be in [0, 255]"
                )
            elif name == "block_size" and (
                type(value) is not int or value < 3 or value % 2 == 0
            ):
                raise BoundaryConfigurationError(
                    "block_size must be an odd integer >= 3"
                )

    @classmethod
    def from_yaml(cls, path: str | Path):
        try:
            data = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
        except yaml.YAMLError as exc:
            raise BoundaryConfigurationError(str(exc)) from exc
        sections = {
            "input": {"require_optimization_quality"},
            "roi": {"padding_ratio", "padding_px", "include_hands"},
            "preprocessing": {"blur_kernel", "illumination"},
            "segmentation": {
                "method",
                "params",
                "hsv",
                "min_roi_stddev",
                "min_foreground_fraction",
                "max_foreground_fraction",
                "min_component_dominance",
                "min_contour_fill_fraction",
                "min_separability",
            },
            "morphology": {
                "open_kernel",
                "close_kernel",
                "iterations",
                "min_component_area_px",
            },
            "contour": {
                "min_area_px",
                "max_area_px",
                "min_perimeter_px",
                "resample_points",
                "resample_spacing_px",
                "border_margin_px",
                "max_border_sides",
                "max_border_point_fraction",
            },
            "chain_code": {"connectivity", "normalize_start_point", "use_differential"},
            "features": {"contact_distance_px", "contact_min_confidence"},
            "temporal": {
                "history_frames",
                "max_missing_frames",
                "max_time_gap_s",
                "motion_min_frames",
                "stationary_tolerance_px",
                "stationary_tolerance",
                "moving_threshold_px",
                "min_motion_coherence",
                "separation_distance_increase_px",
                "rotation_threshold_deg",
                "confirmation_n",
                "confirmation_m",
                "confirmation_min_hits",
                "confirmation_window",
            },
            "crosscheck": {"enabled"},
            "quality": {"require_valid_rack_reference", "min_confidence"},
        }
        if not isinstance(data, dict) or set(data) - set(sections):
            raise BoundaryConfigurationError("invalid boundary configuration sections")
        if any(not isinstance(value, dict) for value in data.values()):
            raise BoundaryConfigurationError("configuration sections must be mappings")
        for section, values in data.items():
            unknown = set(values) - sections[section]
            if unknown:
                raise BoundaryConfigurationError(
                    f"unknown keys in {section}: {sorted(unknown, key=str)}"
                )
        for section, key in (("roi", "include_hands"), ("crosscheck", "enabled")):
            value = data.get(section, {}).get(key, False)
            if type(value) is not bool or value:
                raise BoundaryConfigurationError(
                    f"{section}.{key} must be false: feature not implemented"
                )
        # Source/destination nulls are placeholders: resolve defaults in memory,
        # never downgrade or write back an existing tuned setting.
        mappings = {
            ("input", "require_optimization_quality"): "require_optimization_quality",
            ("roi", "padding_ratio"): "padding_ratio",
            ("roi", "padding_px"): "roi_padding",
            ("preprocessing", "blur_kernel"): "blur_kernel",
            ("segmentation", "method"): "segmentation_method",
            ("segmentation", "params"): "segmentation_params",
            ("morphology", "open_kernel"): "open_kernel",
            ("morphology", "close_kernel"): "close_kernel",
            ("morphology", "iterations"): "iterations",
            ("morphology", "min_component_area_px"): "min_component_area",
            ("contour", "min_area_px"): "min_area",
            ("contour", "max_area_px"): "max_area",
            ("contour", "min_perimeter_px"): "min_perimeter",
            ("features", "contact_distance_px"): "contact_distance_px",
            ("temporal", "history_frames"): "history_frames",
            ("temporal", "max_missing_frames"): "max_missing_frames",
            ("temporal", "max_time_gap_s"): "max_time_gap_s",
            ("chain_code", "normalize_start_point"): "normalize_start_point",
            ("chain_code", "use_differential"): "use_differential",
            ("quality", "require_valid_rack_reference"): "require_valid_rack_reference",
            ("quality", "min_confidence"): "min_confidence",
        }
        for name in (
            "min_roi_stddev",
            "min_foreground_fraction",
            "max_foreground_fraction",
            "min_component_dominance",
            "min_contour_fill_fraction",
            "min_separability",
        ):
            mappings[("segmentation", name)] = name
        for name in (
            "border_margin_px",
            "max_border_sides",
            "max_border_point_fraction",
        ):
            mappings[("contour", name)] = name
        for name in (
            "motion_min_frames",
            "stationary_tolerance_px",
            "moving_threshold_px",
            "min_motion_coherence",
            "separation_distance_increase_px",
            "confirmation_n",
            "confirmation_m",
        ):
            mappings[("temporal", name)] = name
        mappings[("features", "contact_min_confidence")] = "contact_min_confidence"
        temporal = data.get("temporal", {})
        for old, new in (
            ("stationary_tolerance", "stationary_tolerance_px"),
            ("confirmation_min_hits", "confirmation_n"),
            ("confirmation_window", "confirmation_m"),
        ):
            if temporal.get(old) is not None:
                if temporal.get(new) is not None and temporal[new] != temporal[old]:
                    raise BoundaryConfigurationError(
                        f"conflicting temporal aliases: {old}/{new}"
                    )
                mappings[("temporal", old)] = new
        if temporal.get("rotation_threshold_deg") is not None:
            raise BoundaryConfigurationError(
                "rack-relative rotation classification is not implemented"
            )
        values = {
            field_name: data[section][key]
            for (section, key), field_name in mappings.items()
            if data.get(section, {}).get(key) is not None
        }
        if data.get("chain_code", {}).get("connectivity", 8) != 8:
            raise BoundaryConfigurationError(
                "recovered chain code supports connectivity=8 only"
            )
        contour = data.get("contour", {})
        if (
            contour.get("resample_points") is not None
            or contour.get("resample_spacing_px") is not None
        ):
            raise BoundaryConfigurationError(
                "contour resampling is not wired into the recovered core"
            )
        illumination = data.get("preprocessing", {}).get("illumination", {})
        if not isinstance(illumination, dict) or illumination.get("method") not in (
            None,
            "none",
        ):
            raise BoundaryConfigurationError(
                "illumination correction is not implemented"
            )
        if (
            set(illumination) - {"method", "params"}
            or illumination.get("params", {}) != {}
        ):
            raise BoundaryConfigurationError(
                "unknown/unsupported illumination settings"
            )
        hsv = data.get("segmentation", {}).get("hsv", {})
        if (
            not isinstance(hsv, dict)
            or set(hsv) - {"ranges"}
            or hsv.get("ranges", {}) != {}
        ):
            raise BoundaryConfigurationError(
                "HSV segmentation is not implemented; only empty reserved ranges allowed"
            )
        result = cls(**values)
        result.validate()
        return result
