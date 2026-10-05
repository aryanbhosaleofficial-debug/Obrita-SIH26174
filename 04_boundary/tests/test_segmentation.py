"""Actual polarity/quality regressions; only HSV remains future work."""

import cv2
import numpy as np
import pytest
from boundary.boundary_pipeline import BoundaryPipeline
from boundary.config import BoundaryConfig
from boundary.segmentation.mask_cleanup import clean_mask
from boundary.segmentation.segmentation_quality import assess_mask

from shared.enums.module_status import ModuleStatus


@pytest.mark.skip(reason="HSV class ranges are outside current prototype scope")
def test_hsv_ranges_from_config():
    pass


@pytest.mark.parametrize("dark_object", [False, True])
def test_both_polarities_select_object_not_crop_border(image, dark_object):
    pixels = 255 - image if dark_object else image
    before = pixels.copy()
    packet = BoundaryPipeline().process(pixels, 7, 0.5)
    assert packet.quality_ok and packet.status == ModuleStatus.OK
    assert packet.centroid_px == pytest.approx((60, 60))
    assert packet.area_px == pytest.approx(2500, abs=10)
    points = np.asarray(packet.contour_px)
    assert points.min(axis=0) == pytest.approx((35, 35))
    assert points.max(axis=0) == pytest.approx((85, 85))
    assert packet.frame_id == 7 and packet.timestamp_s == 0.5
    np.testing.assert_array_equal(pixels, before)


@pytest.mark.parametrize("intensity", [0, 127, 255])
def test_uniform_scene_has_no_confident_geometry(intensity):
    pixels = np.full((120, 160, 3), intensity, np.uint8)
    packet = BoundaryPipeline().process(pixels, 0, 0)
    assert packet.status == ModuleStatus.NO_DETECTION
    assert not packet.quality_ok and packet.confidence == 0
    assert not packet.contour_px and "low-information ROI" in packet.quality_reasons


@pytest.mark.parametrize("seed", range(5))
def test_random_noise_has_no_confident_geometry(seed):
    pixels = np.random.default_rng(seed).integers(0, 256, (120, 160, 3), dtype=np.uint8)
    packet = BoundaryPipeline().process(pixels, 0, 0)
    assert not packet.quality_ok and packet.confidence == 0
    assert not packet.hand_contact and packet.contact_confidence == 0


def test_bimodal_noise_is_rejected_as_fragmented_foreground():
    pixels = (
        np.random.default_rng(20).choice([0, 255], size=(100, 100)).astype(np.uint8)
    )
    packet = BoundaryPipeline(config=BoundaryConfig(blur_kernel=0)).process(
        pixels, 0, 0
    )
    assert not packet.quality_ok and packet.confidence == 0


def test_roi_fill_is_explicitly_rejected():
    mask = np.full((80, 80), 255, np.uint8)
    gray = np.indices((80, 80))[0].astype(np.uint8)
    assessment = assess_mask(mask, gray, BoundaryConfig())
    assert assessment.contour is None
    assert "foreground occupancy outside configured range" in assessment.reasons


def test_crop_outline_is_not_an_object():
    pixels = np.zeros((120, 160, 3), np.uint8)
    cv2.rectangle(pixels, (0, 0), (159, 119), (255, 255, 255), 2)
    packet = BoundaryPipeline(config=BoundaryConfig(blur_kernel=0)).process(
        pixels, 0, 0
    )
    assert not packet.quality_ok and not packet.contour_px and packet.confidence == 0
    assert any("ROI-border" in reason for reason in packet.quality_reasons)


def test_mask_cleanup_removes_noise():
    mask = np.zeros((40, 40), np.uint8)
    mask[10:25, 10:25] = 255
    mask[0, 0] = 255
    output = clean_mask(mask, min_component_area=10)
    assert output[0, 0] == 0 and output[15, 15] == 255


def test_empty_mask_reported(image):
    packet = BoundaryPipeline().process(np.zeros_like(image), 0, 0)
    assert packet.status == ModuleStatus.NO_DETECTION and not packet.contour_px


def test_source_frame_not_modified(image):
    before = image.copy()
    BoundaryPipeline().process(image, 0, 0)
    np.testing.assert_array_equal(image, before)


def test_canny_silhouette_uses_same_quality_guards(image):
    packet = BoundaryPipeline(
        config=BoundaryConfig(segmentation_method="canny")
    ).process(image, 0, 0)
    assert packet.quality_ok and packet.centroid_px == pytest.approx((60, 60), abs=1)
