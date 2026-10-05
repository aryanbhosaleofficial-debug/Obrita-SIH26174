"""
Module 06 — Live Pose & Hand Tracking (parallel perception branch).

    PreparedFrame -> PoseHandTracker -> PoseFrame   (beside Module 02's ObjectFrame)

Import-safe name: ``pose_tracking`` (root compatibility package).
The numbered directory must never be imported with a normal statement.
No HAR/FSM logic and no camera-"up" semantics live here.
"""

# ruff: noqa: N999 -- numeric owner directory is imported via the pose_tracking alias

_EXPORTS = {
    "PoseFrame": "pose_tracking.contracts",
    "HandPose": "pose_tracking.contracts",
    "Landmark": "pose_tracking.contracts",
    "FrameKey": "pose_tracking.contracts",
    "PoseHandTracker": "pose_tracking.tracker",
    "PoseTrackingConfig": "pose_tracking.config",
    "load_config": "pose_tracking.config",
    "render_overlay": "pose_tracking.visualization",
    "TrackingIntegration": "pose_tracking.integration",
}


def __getattr__(name):
    if name in _EXPORTS:
        from importlib import import_module

        return getattr(import_module(_EXPORTS[name]), name)
    raise AttributeError(name)


__all__ = list(_EXPORTS)
