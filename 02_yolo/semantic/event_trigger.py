"""Direction-independent displacement/appearance triggers; never action labels."""

import math


class EventTrigger:
    def __init__(self, config):
        self.config = config
        self.clear()

    def clear(self):
        self._baseline = None
        self._last_event_s = None

    def check(self, objects):
        # Ambiguous untracked duplicate classes are excluded from motion matching.
        counts = {}
        for d in objects.detections:
            counts[d.class_name] = counts.get(d.class_name, 0) + 1
        current = {
            (d.class_name, d.track_id): d.bbox.center
            for d in objects.detections
            if d.track_id is not None or counts[d.class_name] == 1
        }
        now = objects.timestamp_s
        if self._baseline is None:
            self._baseline = current
            self._last_event_s = now
            return None
        if now - self._last_event_s < self.config.cooldown_s:
            return None
        reason = None
        if current.keys() != self._baseline.keys():
            reason = "object_appearance_change"
        elif any(
            math.hypot(p.x - self._baseline[k].x, p.y - self._baseline[k].y)
            / math.hypot(objects.image_width, objects.image_height)
            >= self.config.displacement_threshold
            for k, p in current.items()
        ):
            reason = "track_displacement"
        elif (
            self.config.interval_s is not None
            and now - self._last_event_s >= self.config.interval_s
        ):
            reason = "manual_interval"
        if reason:
            self._baseline = current
            self._last_event_s = now
        return reason
