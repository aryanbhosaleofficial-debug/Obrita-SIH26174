"""Pair only same-frame, same-operator evidence; no implicit buffering."""


def synchronize(optimization, boundary, config):
    if boundary is None:
        if not config["allow_missing_boundary"]:
            raise ValueError("fusion requires a boundary packet; allow_missing_boundary is false")
        return
    if optimization.frame_id != boundary.frame_id or optimization.target_track_id != boundary.target_track_id:
        raise ValueError("fusion frame/operator mismatch")
    if abs(optimization.timestamp_s - boundary.timestamp_s) > config["max_timestamp_mismatch_s"]:
        raise ValueError("fusion timestamp mismatch")
