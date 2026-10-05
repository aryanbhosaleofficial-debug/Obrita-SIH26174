"""Offline synthetic fixtures; no camera or inference backends."""

import cv2
import numpy as np
import pytest


@pytest.fixture
def image():
    pixels = np.zeros((120, 160, 3), np.uint8)
    cv2.rectangle(pixels, (35, 35), (85, 85), (255, 255, 255), -1)
    return pixels
