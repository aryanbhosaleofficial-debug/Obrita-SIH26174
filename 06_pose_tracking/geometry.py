"""Generic landmark geometry; consumes calibration, never detects a workspace."""
from dataclasses import replace
import math

import numpy as np

from pose_tracking.contracts import Landmark
from shared.schemas.observations import ReferenceFrameInfo


def reference_matrix(workspace: ReferenceFrameInfo | None) -> np.ndarray | None:
    """Validate the existing source-pixel -> normalized rack homography.

    Missing/invalid reference availability is normal. A purportedly valid but
    malformed transform is a caller error; never silently mix coordinate frames.
    """
    if workspace is not None and not isinstance(workspace, ReferenceFrameInfo):
        raise TypeError("workspace must be shared ReferenceFrameInfo")
    if workspace is None or not workspace.valid:
        return None
    matrix = np.asarray(workspace.image_to_reference_matrix, dtype=float)
    if matrix.shape != (3, 3) or not np.isfinite(matrix).all():
        raise ValueError("valid workspace requires a finite 3x3 image-to-rack matrix")
    scale = np.max(np.abs(matrix))
    if scale == 0 or np.linalg.matrix_rank(matrix / scale) != 3:
        raise ValueError("image-to-rack matrix must be nonsingular")
    return matrix


def normalize_landmarks(points: tuple[Landmark, ...], width: int, height: int,
                        matrix: np.ndarray | None = None) -> tuple[Landmark, ...]:
    """Add camera XY and optional rack XY after pixel EMA; depth stays relative.

    Extrapolated camera coordinates are retained rather than clamped. Points on
    a homography's horizon cannot have a finite rack position and become invalid.
    """
    if width <= 0 or height <= 0:
        raise ValueError("coordinate conversion requires positive source dimensions")
    result = []
    for point in points:
        rack = None
        valid = point.is_valid
        if matrix is not None and valid:
            projected = matrix @ [point.x, point.y, 1.0]
            if not np.isfinite(projected).all() or abs(projected[2]) < 1e-12:
                valid = False
            else:
                xy = projected[:2] / projected[2]
                if np.isfinite(xy).all():
                    rack = (float(xy[0]), float(xy[1]))
                else:
                    valid = False
        result.append(replace(point, is_valid=valid,
                              normalized_xy=(point.x / width, point.y / height), rack_xy=rack))
    return tuple(result)


def hand_bbox(points: tuple[Landmark, ...], width: int, height: int,
              padding: float = 0.02) -> tuple[float, float, float, float] | None:
    """Padded box from valid joints, clipped to the pixel-edge domain [0,W]x[0,H]."""
    if width <= 0 or height <= 0 or not math.isfinite(padding) or not 0 <= padding <= 1:
        raise ValueError("positive image dimensions and padding in [0,1] required")
    valid = [p for p in points if p.is_valid]
    if not valid:
        return None
    x1, x2 = min(p.x for p in valid), max(p.x for p in valid)
    y1, y2 = min(p.y for p in valid), max(p.y for p in valid)
    clamp_x = lambda x: max(0.0, min(float(width), x))
    clamp_y = lambda y: max(0.0, min(float(height), y))
    box = (clamp_x(x1 - padding * width), clamp_y(y1 - padding * height),
           clamp_x(x2 + padding * width), clamp_y(y2 + padding * height))
    return box if box[0] < box[2] and box[1] < box[3] else None
