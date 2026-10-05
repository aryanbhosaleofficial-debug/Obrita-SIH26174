"""Select a current stable target; never interpret held or ambiguous boxes."""


def target(optimization, boundary):
    objects = optimization.object_frame
    if objects is None or not optimization.quality_ok:
        return None, None
    detections = [(i, d) for i, d in enumerate(objects.detections) if d.is_stable and not d.is_context and not d.identity_ambiguous and d.frames_since_seen == 0 and (d.continuity_key is not None or d.track_id is not None)]
    track = boundary.target_object_track_id if boundary else None
    if track is not None:
        detections = [(i, d) for i, d in detections if d.track_id == track]
    return detections[0] if len(detections) == 1 else (None, None)


def extract(detection):
    return (detection.class_name, detection.confidence) if detection else None
