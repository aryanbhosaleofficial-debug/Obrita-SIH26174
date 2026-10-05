"""Actual contour/border assertions; association and resampling remain deferred."""

import numpy as np
import pytest
from boundary.boundary_pipeline import BoundaryPipeline
from boundary.config import BoundaryConfig
from boundary.contour.contour_extractor import extract_contours
from boundary.contour.contour_validator import border_metrics, validate_contour
from boundary.segmentation.foreground_segmenter import segment
from boundary.segmentation.segmentation_quality import assess_mask


def test_contour_offset_to_original_frame(image):
    contours = extract_contours(segment(image[25:95, 25:95]), (25, 25))
    assert np.asarray(contours[0]).min(axis=0) == pytest.approx((35, 35))


@pytest.mark.skip(reason="Multi-contour target overlap association not implemented")
def test_association_picks_target():
    pass


def test_small_contour_rejected():
    valid, _, reason = validate_contour([(0, 0), (1, 0), (0, 1)], min_area=20)
    assert not valid and "area" in reason


@pytest.mark.skip(reason="Contours remain dense; resampling not implemented")
def test_resampling_uniform():
    pass


def test_roi_border_contour_is_rejected_even_when_solidity_is_one():
    mask = np.zeros((80, 80), np.uint8)
    mask[[0, -1], :] = 255
    mask[:, [0, -1]] = 255
    contour = extract_contours(mask)[0]
    assert border_metrics(contour, mask.shape)["sides_touched"] == 4
    assessment = assess_mask(mask, mask, BoundaryConfig(blur_kernel=0))
    assert (
        assessment.contour is None
        and "ROI-border contour rejected" in assessment.reasons
    )


def test_legitimate_object_touching_one_side_is_not_automatically_rejected():
    pixels = np.zeros((100, 100), np.uint8)
    pixels[30:70, :35] = 255
    packet = BoundaryPipeline(config=BoundaryConfig(blur_kernel=0)).process(
        pixels, 0, 0
    )
    assert packet.quality_ok and packet.contour_px
    assert packet.centroid_px == pytest.approx((17, 49.5))
