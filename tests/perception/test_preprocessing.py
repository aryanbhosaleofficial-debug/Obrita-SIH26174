from dataclasses import replace

import numpy as np
import pytest

from perception.config import PreprocessingConfig
from perception.contracts import BoundingBox, Point2D
from perception.preprocessing import InvalidFrameError, preprocess


def test_resize_restore_and_copy(packet, scene):
    source = packet(image=np.full((241, 320, 3), 100, np.uint8))
    processed = preprocess(source, PreprocessingConfig(max_width=160))
    assert processed.image.shape == (120, 160, 3)
    assert processed.source_point(Point2D(80, 60)) == Point2D(160, 120.5)
    detection = scene[0][0]
    restored = processed.source_detection(detection)
    assert restored.bbox == BoundingBox(240, 80 / (120 / 241), 400, 160 / (120 / 241))
    processed.image[:] = 0
    assert np.all(source.image == 100)


def test_rgb_conversion_and_luminance(packet):
    image = np.zeros((32, 32, 3), np.uint8)
    image[..., 0] = 200
    source = replace(packet(image=image), color_format="RGB")
    result = preprocess(source, PreprocessingConfig())
    assert result.image[0, 0].tolist() == [0, 0, 200]
    equalized = preprocess(source, PreprocessingConfig(equalize_luminance=True))
    assert equalized.image.shape == image.shape
    assert np.array_equal(source.image, image)


@pytest.mark.parametrize(
    "change",
    [
        {"image": None},
        {"image": np.zeros((2, 2), np.uint8)},
        {"image": np.zeros((240, 320, 3), np.float32)},
        {"image": np.zeros((0, 320, 3), np.uint8)},
        {"width": 999},
        {"frame_id": -1},
        {"frame_id": True},
        {"timestamp_s": float("nan")},
        {"timestamp_s": True},
        {"color_format": "GRAY"},
        {"source_id": ""},
    ],
)
def test_invalid_frame(packet, change):
    with pytest.raises(InvalidFrameError):
        preprocess(replace(packet(), **change), PreprocessingConfig())
