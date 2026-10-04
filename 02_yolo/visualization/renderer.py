"""Original-source-pixel overlays, always on a detached BGR display image."""

import cv2
import numpy as np


class VisualizationError(ValueError):
    pass


def source_bgr(source):
    image = source.image
    if not isinstance(image, np.ndarray) or image.dtype != np.uint8 or image.size == 0:
        raise VisualizationError("display source requires a nonempty uint8 image")
    color = source.color_format
    if color == "RGB" and image.ndim == 3 and image.shape[2] == 3:
        return cv2.cvtColor(image, cv2.COLOR_RGB2BGR)
    if color in ("GRAY", "GREY") and image.ndim == 2:
        return cv2.cvtColor(image, cv2.COLOR_GRAY2BGR)
    if color == "BGR" and image.ndim == 3 and image.shape[2] == 3:
        return image
    raise VisualizationError("unsupported source display color format")


class FrameRenderer:
    def render(
        self, source, objects, semantic=None, *, vlm_status="DISABLED", tracking=False
    ):
        """Use prepared.source in SIH mode. Resized prepared images are rejected."""
        try:
            image = source_bgr(source)
            if (
                image.shape[:2] != (objects.image_height, objects.image_width)
                or source.frame_id != objects.frame_id
                or source.source_id != objects.source_id
                or source.session_id != objects.session_id
                or source.timestamp_s != objects.timestamp_s
            ):
                raise VisualizationError(
                    "source frame does not match source-coordinate detections"
                )
            display = image.copy()
            h, w = display.shape[:2]
            for d in objects.detections:
                x1, y1, x2, y2 = (round(v) for v in d.bbox_xyxy)
                p1, p2 = (
                    (max(0, min(w - 1, x1)), max(0, min(h - 1, y1))),
                    (max(0, min(w - 1, x2)), max(0, min(h - 1, y2))),
                )
                cv2.rectangle(display, p1, p2, (0, 255, 0), 2)
                label = f"{d.class_name} {d.confidence:.2f}" + (
                    f" ID:{d.track_id}" if d.track_id is not None else ""
                )
                cv2.putText(
                    display,
                    label,
                    (p1[0], max(15, p1[1] - 5)),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.5,
                    (0, 255, 0),
                    1,
                )
            yolo_status = getattr(objects.status, "value", objects.status)
            track_status = (
                "OFF"
                if not tracking
                else "ON"
                if all(d.track_id is not None for d in objects.detections)
                else "IDENTITY_UNAVAILABLE"
            )
            if any(
                getattr(warning, "details", {}).get("stage") == "tracker_reset"
                for warning in objects.warnings
            ):
                track_status = "ERROR"
            lines = [
                f"Frame:{objects.frame_id} YOLO:{yolo_status} Tracking:{track_status}",
                f"VLM:{getattr(vlm_status, 'value', vlm_status)}",
            ]
            if semantic:
                lines.append(
                    f"Last semantic event:{semantic.event_id} {semantic.action}"
                )
                lines.append(
                    f"Frame:{semantic.frame_id} Time:{semantic.timestamp_s:.3f}s {semantic.status.value}"
                )
            for i, text in enumerate(lines):
                cv2.putText(
                    display,
                    text,
                    (8, 22 + i * 22),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.5,
                    (255, 255, 255),
                    2,
                )
            return display
        except (cv2.error, TypeError, OverflowError) as exc:
            raise VisualizationError(f"render failed: {exc}") from exc
