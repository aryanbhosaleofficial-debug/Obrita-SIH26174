"""Actual ArUco detection at four image rotations; no camera or models needed."""

import json

import numpy as np
from optimization.reference_frame.coordinate_frame import ArucoCoordinateTransformer

from integration.marker_scene import marker_board
from shared.schemas.observations import Point2D


def run():
    transformer = ArucoCoordinateTransformer()
    for turns in range(4):
        board = np.rot90(marker_board(), turns).copy()
        info = transformer.update(board)
        if not info.valid:
            raise RuntimeError(f"marker detection failed at {turns * 90} degrees")
        center = transformer.image_to_reference(Point2D(199.5, 199.5), board.shape[:2])
        print(
            json.dumps(
                {
                    "rotation_degrees_ccw": turns * 90,
                    "source": info.source,
                    "verified_this_frame": info.verified_this_frame,
                    "rack_center": [center.x, center.y],
                }
            )
        )


if __name__ == "__main__":
    run()
