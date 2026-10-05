"""Focused checks for recovered helpers and bounded target geometry history."""

import subprocess
import sys
from collections import deque

import numpy as np
import pytest
from boundary.chain_code.chain_normalizer import normalize_chain_code
from boundary.contour.contour_extractor import extract_contours
from boundary.contour.contour_validator import validate_contour
from boundary.features.hand_boundary_features import hand_boundary_interaction
from boundary.roi.boundary_roi import extract_roi
from boundary.segmentation.foreground_segmenter import segment
from boundary.segmentation.mask_cleanup import clean_mask
from boundary.temporal.boundary_tracker import BoundaryTracker


def test_roi_offsets_and_source_ownership(image):
    before = image.copy()
    crop = extract_roi(image, (25, 25, 80, 80), padding=3)
    assert crop.offset == (22, 22) and crop.valid
    contours = extract_contours(segment(crop.image), crop.offset)
    assert contours and validate_contour(contours[0], min_area=20)[0]
    np.testing.assert_array_equal(image, before)


def test_component_cleanup_and_invalid_small_contour():
    mask = np.zeros((50, 50), np.uint8)
    mask[10:30, 10:30] = 255
    mask[0, 0] = 255
    cleaned = clean_mask(mask, min_component_area=10)
    assert cleaned[0, 0] == 0 and cleaned[20, 20] == 255
    assert not validate_contour([(0, 0), (1, 0), (0, 1)], min_area=20)[0]


def test_contact_checks_all_hands_and_remains_distance_evidence():
    contour = np.array([(10, 10), (30, 10), (30, 30), (10, 30)], dtype=float)
    result = hand_boundary_interaction(
        contour,
        [
            {"hand_id": "far", "point": (100, 100)},
            {"hand_id": "near", "point": (10, 20)},
        ],
    )
    assert result["hand_id"] == "near" and result["near_boundary"]
    assert result["contact_proxy"] == 1
    assert len(result["hands"]) == 2
    assert hand_boundary_interaction(None)["available"] is False


def test_tracker_history_expiry_and_reset():
    tracker = BoundaryTracker(history=deque(maxlen=3), max_missing_frames=2)
    for i in range(100):
        tracker.update(np.array([(0, 0), (1, 0), (0, 1)]), (i, 0), i, i / 30, 0.9)
        assert len(tracker.history) <= 3
    tracker.mark_missing(2)
    assert tracker.history
    tracker.mark_missing()
    assert not tracker.history
    tracker.reset()
    assert tracker.missed == 0


@pytest.mark.parametrize(
    "sequence",
    [
        [],
        [0],
        [1, 1, 1],
        [7, 0, 0, 2, 4],
        [6, 6, 0, 0, 2, 2, 4, 4],
    ],
)
def test_minimum_rotation_keeps_every_step(sequence):
    expected = min(
        (sequence[i:] + sequence[:i] for i in range(len(sequence))), default=[]
    )
    assert normalize_chain_code(sequence) == expected
    assert len(normalize_chain_code(sequence)) == len(sequence)


def test_core_import_and_processing_are_offline_and_model_free():
    code = """
import socket,sys,importlib
def forbidden(*args, **kwargs): raise AssertionError('network used')
socket.socket.connect = forbidden
socket.create_connection = forbidden
import numpy as np,cv2
m=importlib.import_module('04_boundary.boundary_pipeline')
image=np.zeros((80,80,3),np.uint8)
cv2.rectangle(image,(20,20),(60,60),(255,255,255),-1)
assert m.BoundaryPipeline().process(image,0,0).quality_ok
assert not any(k.split('.')[0] in {'torch','ultralytics','mediapipe','streamlit','optimization','yolo'} for k in sys.modules)
"""
    subprocess.run([sys.executable, "-c", code], check=True)
