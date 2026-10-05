"""Replaceable rack calibration; never infer physical up from the camera. """

from __future__ import annotations

from collections.abc import Sequence

import cv2
import numpy as np

from shared.geometry import (
    CoordinateTransformer,  # noqa: F401 -- public protocol re-export
    ReferenceUnavailableError,
    normalized_point,
    validate_corners,
)
from shared.schemas.observations import Point2D, ReferenceFrameInfo, ReferenceSource


class UnavailableReference:
    def update(self, image: np.ndarray) -> ReferenceFrameInfo:
        return ReferenceFrameInfo()

    def image_to_reference(
        self, point: Point2D, frame_shape: tuple[int, int]
    ) -> Point2D:
        raise ReferenceUnavailableError("reference calibration unavailable")


class ManualRackTransformer:
    """Fixed camera/board homography to a unit rack square.

    Corners follow physical rack order: (0,0), (1,0), (1,1), (0,1).
    Their image order can be rotated arbitrarily. This manual calibration cannot
    detect movement of the camera/rack: recalibrate or invalidate it externally.
    """

    def __init__(
        self, corners_normalized: Sequence[Sequence[float]], reference_id: str = "rack"
    ):
        points = validate_corners(corners_normalized)
        self._matrix_normalized = cv2.getPerspectiveTransform(
            points.astype(np.float32),
            np.array([[0, 0], [1, 0], [1, 1], [0, 1]], dtype=np.float32),
        ).astype(np.float64)
        self.reference_id = reference_id
        self._points = points
        self.valid = True

    def image_to_reference(
        self, point: Point2D, frame_shape: tuple[int, int]
    ) -> Point2D:
        if not self.valid:
            raise ReferenceUnavailableError("manual reference invalidated")
        p = normalized_point(point, frame_shape)
        value = self._matrix_normalized @ np.array([p.x, p.y, 1.0])
        if not np.isfinite(value).all() or abs(value[2]) < 1e-9:
            raise ReferenceUnavailableError(
                "point lies on reference projective horizon"
            )
        return Point2D(float(value[0] / value[2]), float(value[1] / value[2]))

    def update(self, image: np.ndarray) -> ReferenceFrameInfo:
        if not self.valid:
            return ReferenceFrameInfo(
                reference_id=self.reference_id, source=ReferenceSource.STATIC_MANUAL
            )
        height, width = image.shape[:2]
        matrix = self._matrix_normalized @ np.diag([1 / width, 1 / height, 1])

        # Axes drawn from origin toward the physical +x and +y rack corners.
        def pixel_corner(index: int) -> Point2D:
            return Point2D(
                float(self._points[index, 0] * width),
                float(self._points[index, 1] * height),
            )

        axes = (pixel_corner(0), pixel_corner(1), pixel_corner(3))
        return ReferenceFrameInfo(
            True,
            self.reference_id,
            tuple(tuple(float(v) for v in row) for row in matrix),
            axes,
            source=ReferenceSource.STATIC_MANUAL,
            verified_this_frame=False,
        )


class ArucoCoordinateTransformer:
    """Four marker centers in physical rack order; recalibrated on every frame.

    IDs encode origin,+x,+x/+y,+y. Marker loss invalidates immediately; there is
    no silent retention of the last transform. Units span marker centers.
    """

    def __init__(
        self,
        marker_ids=(0, 1, 2, 3),
        dictionary="DICT_4X4_50",
        reference_id="rack_aruco",
    ):
        if not hasattr(cv2, "aruco") or not hasattr(cv2.aruco, "ArucoDetector"):
            raise ValueError(
                "ArUco requires an OpenCV build exposing aruco.ArucoDetector"
            )
        if len(marker_ids) != 4 or len(set(marker_ids)) != 4:
            raise ValueError("four distinct marker IDs are required")
        if not hasattr(cv2.aruco, dictionary) or not dictionary.startswith("DICT_"):
            raise ValueError("unknown ArUco dictionary")
        self.dictionary = cv2.aruco.getPredefinedDictionary(
            getattr(cv2.aruco, dictionary)
        )
        if any(
            type(i) is not int or i < 0 or i >= len(self.dictionary.bytesList)
            for i in marker_ids
        ):
            raise ValueError("marker ID outside dictionary")
        self.detector = cv2.aruco.ArucoDetector(
            self.dictionary, cv2.aruco.DetectorParameters()
        )
        self.marker_ids = tuple(marker_ids)
        self.reference_id = reference_id
        self._manual = None

    def update(self, image: np.ndarray) -> ReferenceFrameInfo:
        self._manual = None
        corners, ids, _ = self.detector.detectMarkers(
            cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        )
        if ids is None:
            return ReferenceFrameInfo(source=ReferenceSource.ARUCO)
        found = {}
        for marker_corners, marker_id in zip(corners, ids.flatten()):
            identifier = int(marker_id)
            if identifier in found:
                return ReferenceFrameInfo(source=ReferenceSource.ARUCO)
            found[identifier] = marker_corners.reshape(-1, 2).mean(axis=0)
        if not all(i in found for i in self.marker_ids):
            return ReferenceFrameInfo(source=ReferenceSource.ARUCO)
        height, width = image.shape[:2]
        normalized = [
            [float(found[i][0] / width), float(found[i][1] / height)]
            for i in self.marker_ids
        ]
        try:
            self._manual = ManualRackTransformer(normalized, self.reference_id)
        except ValueError:
            return ReferenceFrameInfo(source=ReferenceSource.ARUCO)
        info = self._manual.update(image)
        info.source = ReferenceSource.ARUCO
        info.verified_this_frame = True
        return info

    def image_to_reference(
        self, point: Point2D, frame_shape: tuple[int, int]
    ) -> Point2D:
        if self._manual is None:
            raise ReferenceUnavailableError(
                "required markers are not visible in the current frame"
            )
        return self._manual.image_to_reference(point, frame_shape)
