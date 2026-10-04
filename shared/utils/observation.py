"""Evidence confidence and input validation helpers."""

import math

from shared.schemas.observations import ObservationConfidence, Point2D


def valid_score(score: float | None) -> bool:
    return score is None or (
        isinstance(score, (float, int))
        and not isinstance(score, bool)
        and math.isfinite(score)
        and 0 <= score <= 1
    )


def valid_point(point: Point2D) -> bool:
    return math.isfinite(point.x) and math.isfinite(point.y)


def combine_confidence(
    detector: float | None = None,
    tracker: float | None = None,
    geometry: float | None = None,
) -> ObservationConfidence:
    """Minimum known components, not a product or probability of physical contact.

    Missing components remain None. Geometry is a threshold-based heuristic.
    """
    values = [v for v in (detector, tracker, geometry) if v is not None]
    if not all(valid_score(v) for v in values):
        raise ValueError("confidence components must be finite scores in [0, 1]")
    return ObservationConfidence(
        detector, tracker, geometry, min(values) if values else None
    )
