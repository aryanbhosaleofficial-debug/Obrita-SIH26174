import math

import numpy as np
import pytest

from perception.contracts import Point2D
from perception.coordinate_frame import (
    ManualRackTransformer,
    ReferenceUnavailableError,
    normalized_point,
)


def test_normalized_conversion():
    assert normalized_point(Point2D(80, 120), (240, 320)) == Point2D(0.25, 0.5)
    with pytest.raises(ValueError):
        normalized_point(Point2D(1, 1), (0, 100))


@pytest.mark.parametrize("angle", [0, 90, 180, 37, -64])
def test_rotated_physical_reference(angle):
    rotation = np.array(
        [
            [math.cos(math.radians(angle)), -math.sin(math.radians(angle))],
            [math.sin(math.radians(angle)), math.cos(math.radians(angle))],
        ]
    )
    corners = (
        np.array([[-0.25, -0.25], [0.25, -0.25], [0.25, 0.25], [-0.25, 0.25]])
        @ rotation.T
        + 0.5
    )
    transformer = ManualRackTransformer(corners)
    point = np.array([-0.15, 0.1]) @ rotation.T + 0.5  # physical rack (0.2, 0.7)
    mapped = transformer.image_to_reference(
        Point2D(point[0] * 640, point[1] * 480), (480, 640)
    )
    assert mapped.x == pytest.approx(0.2, abs=1e-6)
    assert mapped.y == pytest.approx(0.7, abs=1e-6)
    info = transformer.update(np.zeros((480, 640, 3), np.uint8))
    matrix = np.asarray(info.image_to_reference_matrix)
    projected = matrix @ np.array([point[0] * 640, point[1] * 480, 1])
    assert projected[:2] / projected[2] == pytest.approx([0.2, 0.7], abs=1e-6)
    assert info.valid and info.axes_pixels


def test_perspective_and_invalidation():
    transformer = ManualRackTransformer(
        [[0.1, 0.2], [0.8, 0.1], [0.9, 0.9], [0.2, 0.7]]
    )
    for p, expected in zip(
        [[0.1, 0.2], [0.8, 0.1], [0.9, 0.9], [0.2, 0.7]],
        [[0, 0], [1, 0], [1, 1], [0, 1]],
    ):
        mapped = transformer.image_to_reference(
            Point2D(p[0] * 100, p[1] * 100), (100, 100)
        )
        assert [mapped.x, mapped.y] == pytest.approx(expected, abs=1e-6)
    transformer.valid = False
    assert not transformer.update(np.zeros((100, 100, 3), np.uint8)).valid
    with pytest.raises(ReferenceUnavailableError):
        transformer.image_to_reference(Point2D(50, 50), (100, 100))


@pytest.mark.parametrize(
    "corners",
    [
        [],
        [[0, 0]] * 4,
        [[0, 0], [1, 1], [1, 0], [0, 1]],
        [[0, 0], [2, 0], [1, 1], [0, 1]],
        [[0, 0], [1, 0], [float("nan"), 1], [0, 1]],
    ],
)
def test_invalid_calibration(corners):
    with pytest.raises(ValueError):
        ManualRackTransformer(corners)
