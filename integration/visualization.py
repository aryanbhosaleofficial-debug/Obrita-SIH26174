"""Optional overlays on a copy; never part of the perception data contract."""

import cv2
import numpy as np

from shared.config import DebugConfig
from shared.schemas.observations import PerceptionFrameResult, Point2D


def draw_perception_overlay(
    frame: np.ndarray, result: PerceptionFrameResult, options: DebugConfig | None = None
) -> np.ndarray:
    """Draw original-source pixel geometry without mutating frame/result."""
    if (
        frame.dtype != np.uint8
        or frame.ndim != 3
        or frame.shape[2] != 3
        or frame.shape[:2] != (result.image_height, result.image_width)
    ):
        raise ValueError("overlay needs uint8 BGR frame matching result dimensions")
    options = options or DebugConfig()
    output = frame.copy()

    def pixel(point: Point2D) -> tuple[int, int]:
        return round(point.x), round(point.y)

    if options.draw_detections:
        for detection in result.detections:
            b = detection.bbox
            color = (0, 220, 0) if detection.is_stable else (0, 180, 255)
            cv2.rectangle(
                output, (round(b.x1), round(b.y1)), (round(b.x2), round(b.y2)), color, 2
            )
            identity = (
                f" id={detection.track_id}" if detection.track_id is not None else ""
            )
            cv2.putText(
                output,
                f"{detection.class_name} {detection.confidence:.2f}{identity}",
                (round(b.x1), max(12, round(b.y1) - 4)),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.4,
                color,
                1,
            )
    if options.draw_hands:
        for hand in result.hands:
            for landmark in hand.landmarks:
                cv2.circle(output, pixel(landmark), 2, (255, 180, 0), -1)
            cv2.circle(output, pixel(hand.palm_center), 4, (255, 80, 0), 1)
    if (
        options.draw_reference_axes
        and result.coordinate_frame_valid
        and result.reference_frame.axes_pixels
    ):
        origin, x_axis, y_axis = result.reference_frame.axes_pixels
        for endpoint, label, color in (
            (x_axis, "rack +x", (0, 0, 255)),
            (y_axis, "rack +y", (0, 255, 0)),
        ):
            cv2.arrowedLine(output, pixel(origin), pixel(endpoint), color, 2)
            cv2.putText(
                output, label, pixel(endpoint), cv2.FONT_HERSHEY_SIMPLEX, 0.4, color, 1
            )
    if options.draw_associations:
        for association in result.associations:
            if association.near:
                hand = result.hands[association.hand_index]
                detection = result.detections[association.detection_index]
                cv2.line(
                    output,
                    pixel(hand.palm_center),
                    pixel(detection.bbox.center),
                    (0, 0, 255) if association.ambiguous else (255, 0, 255),
                    1,
                )
    if options.draw_warnings:
        for index, warning in enumerate(result.warnings):
            cv2.putText(
                output,
                warning.code.value,
                (5, 15 + index * 15),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.35,
                (0, 0, 255),
                1,
            )
    return output
