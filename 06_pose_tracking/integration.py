"""Narrow adapter from the existing Modules 01–05 result to Module 06.

ActivityEvent has identity/evidence but no image. Use upstream.prepared and
consume upstream.optimization.spatial.reference_frame without detecting a rack
or interpreting the activity. Existing owners retain every processing stage.
"""
from __future__ import annotations
from typing import TYPE_CHECKING

from pose_tracking.contracts import PoseFrame
from pose_tracking.sync import FrameSyncError, require_synchronized
from pose_tracking.tracker import PoseHandTracker

if TYPE_CHECKING:
    from integration.milestone import MilestoneResult


class TrackingIntegration:
    """Frame-synchronous adapter; the caller owns pipeline/tracker lifecycles."""

    def __init__(self, tracker: PoseHandTracker):
        self.tracker = tracker

    def process(self, milestone: MilestoneResult) -> PoseFrame:
        """Consume integration.milestone.MilestoneResult; return only tracking."""
        from integration.milestone import MilestoneResult

        if not isinstance(milestone, MilestoneResult):
            raise TypeError("TrackingIntegration consumes MilestoneResult")
        prepared = milestone.upstream.prepared
        source = prepared.source
        if source is None:
            raise FrameSyncError("milestone must retain the source FramePacket")
        require_synchronized(prepared, milestone.upstream.objects)
        if (milestone.upstream.objects.image_width, milestone.upstream.objects.image_height) != (source.width, source.height):
            raise FrameSyncError("object coordinates differ from source dimensions")
        optimized = milestone.upstream.optimization
        for packet in (milestone.upstream.objects, optimized, milestone.boundary, milestone.activity):
            if packet.frame_id != source.frame_id or packet.timestamp_s != source.timestamp_s:
                raise FrameSyncError("Module 06 input packets describe different source frames")
        for name in ("source_id", "session_id"):
            value = milestone.activity.metadata.get(name)
            if value is not None and value != getattr(source, name):
                raise FrameSyncError(f"Module 05 {name} differs from the retained source")
        spatial = optimized.spatial
        if spatial is not None and (spatial.frame_id != source.frame_id or spatial.timestamp_s != source.timestamp_s):
            raise FrameSyncError("spatial reference describes a different source frame")
        return self.tracker.process(prepared, workspace=spatial.reference_frame if spatial else None)
