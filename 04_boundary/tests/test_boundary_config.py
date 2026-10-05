"""Preserve existing YAML, honor wired values, and reject invalid settings."""

from pathlib import Path

import pytest
from boundary.boundary_pipeline import BoundaryPipeline
from boundary.config import BoundaryConfig, BoundaryConfigurationError


@pytest.mark.parametrize(
    "values",
    [
        {"history_frames": 0},
        {"max_missing_frames": -1},
        {"min_area": -1},
        {"blur_kernel": 4},
        {"contact_distance_px": 0},
        {"max_time_gap_s": 0},
        {"min_confidence": 2},
        {"min_confidence": float("nan")},
        {"segmentation_method": "cloud"},
        {"max_area": 1},
        {"iterations": 0},
        {"require_optimization_quality": "yes"},
        {"segmentation_params": {"threshold": float("nan")}},
        {"segmentation_method": "adaptive", "segmentation_params": {"block_size": 4}},
        {"min_roi_stddev": 0},
        {"max_foreground_fraction": 1},
        {"min_foreground_fraction": 0.95},
        {"min_component_dominance": 0},
        {"min_separability": float("nan")},
        {"max_border_sides": 4},
        {"border_margin_px": -1},
        {"confirmation_n": 0},
        {"confirmation_n": 4, "confirmation_m": 3},
        {"history_frames": 2},
        {"motion_min_frames": 2},
        {"moving_threshold_px": 0.5},
        {"min_motion_coherence": 2},
    ],
)
def test_invalid_settings(values):
    with pytest.raises(BoundaryConfigurationError):
        BoundaryConfig(**values).validate()


def test_existing_configuration_is_read_only_and_effective():
    path = Path(__file__).resolve().parents[2] / "configs/boundary.yaml"
    before = path.read_bytes()
    config = BoundaryConfig.from_yaml(path)
    assert config.min_area == 20 and config.history_frames == 20
    assert config.require_optimization_quality and config.require_valid_rack_reference
    assert path.read_bytes() == before


def test_tuned_values_preserved_and_wired(tmp_path):
    path = tmp_path / "boundary.yaml"
    path.write_text(
        "roi: {padding_ratio: 0.2}\npreprocessing: {blur_kernel: 5}\n"
        "segmentation: {method: canny, params: {low: 30, high: 90}}\n"
        "contour: {min_area_px: 100, max_area_px: 2000}\n"
        "temporal: {history_frames: 8}\nquality: {min_confidence: 0.6}",
        encoding="utf-8",
    )
    config = BoundaryConfig.from_yaml(path)
    assert (
        config.padding_ratio,
        config.blur_kernel,
        config.min_area,
        config.max_area,
        config.history_frames,
        config.min_confidence,
    ) == (0.2, 5, 100, 2000, 8, 0.6)
    assert config.segmentation_params == {"low": 30, "high": 90}


@pytest.mark.parametrize(
    "text",
    [
        "[]",
        "roi: []",
        "unknown: {}",
        "chain_code: {connectivity: 4}",
        "contour: {resample_points: 8}",
        "preprocessing: {illumination: {method: histogram}}",
        "roi: {paddding_ratio: 0.2}",
        "quality: {min_confidnce: 0.5}",
        "temporal: {confirmation_n: 4, confirmation_m: 3}",
        "temporal: {confirmation_n: 2, confirmation_min_hits: 3}",
        "temporal: {rotation_threshold_deg: 5}",
        "segmentation: {hsv: {ranges: {vial: {lower: [0, 0, 0]}}}}",
        "segmentation: {params: {threshhold: 20}}",
        "preprocessing: {illumination: {method: none, typo: 1}}",
        "crosscheck: {enabled: true}",
        "roi: {include_hands: true}",
    ],
)
def test_unsupported_configuration_is_explicit(tmp_path, text):
    path = tmp_path / "boundary.yaml"
    path.write_text(text, encoding="utf-8")
    with pytest.raises(BoundaryConfigurationError):
        BoundaryConfig.from_yaml(path)


def test_legacy_temporal_aliases_are_wired_and_null_is_explicit_default(tmp_path):
    path = tmp_path / "boundary.yaml"
    path.write_text(
        "temporal: {confirmation_min_hits: 3, confirmation_window: 5, stationary_tolerance: 0.5}\npreprocessing: {blur_kernel: null}",
        encoding="utf-8",
    )
    config = BoundaryConfig.from_yaml(path)
    assert (
        config.confirmation_n,
        config.confirmation_m,
        config.stationary_tolerance_px,
        config.blur_kernel,
    ) == (3, 5, 0.5, 3)


def test_strict_confidence_can_warm_trusted_geometry_without_publishing_contact(image):
    pipeline = BoundaryPipeline(config=BoundaryConfig(min_confidence=0.95))
    hand = [{"hand_id": "hand-1", "point": (35, 60)}]
    first = pipeline.process(image, 0, 0, hand_data=hand)
    assert not first.quality_ok and first.confidence == first.contact_confidence == 0
    assert not first.hand_contact and not first.state_confirmed
    second = pipeline.process(image, 1, 1 / 30, hand_data=hand)
    assert second.quality_ok and second.hand_contact and not second.state_confirmed
