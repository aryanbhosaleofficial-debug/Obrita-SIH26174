"""Authoritative sequential Modules 01–05 composition; no procedure/GUI logic."""
from dataclasses import dataclass
from time import perf_counter

from boundary.boundary_pipeline import BoundaryPipeline
from fusion.pipeline import FusionPipeline
from integration.chain import ChainResult, PerceptionChain
from shared.schemas.activity_event import ActivityEvent
from shared.schemas.boundary_packet import BoundaryOutputPacket


@dataclass
class MilestoneResult:
    upstream: ChainResult
    boundary: BoundaryOutputPacket
    activity: ActivityEvent
    timings_ms: dict


class MilestonePipeline:
    def __init__(self, chain, boundary=None, fusion=None, *, target_object_track_id=None):
        self.chain = chain
        self.boundary = boundary or BoundaryPipeline()
        self.fusion = fusion or FusionPipeline()
        self.target_object_track_id = target_object_track_id

    def initialize(self):
        self.chain.initialize()

    def process(self, frame):
        started = perf_counter()
        upstream = self.chain.process(frame)
        if upstream.prepared.reset_required:
            self.boundary.reset()
            self.fusion.reset()
        t = perf_counter()
        from shared.enums.module_status import ModuleStatus
        unusable = any(part.status in (ModuleStatus.ERROR, ModuleStatus.INVALID_INPUT)
                       for part in (upstream.prepared, upstream.objects, upstream.optimization))
        if unusable:
            boundary = BoundaryOutputPacket(
                frame.frame_id, frame.timestamp_s, status=ModuleStatus.INVALID_INPUT,
                quality_reasons=["upstream error/invalid_input"],
            )
        else:
            boundary = self.boundary.process_optimization(
                upstream.optimization, frame,
                target_object_track_id=self.target_object_track_id,
            )
        boundary_ms = (perf_counter() - t) * 1000
        # Fatal/invalid upstream packets are not fused. Record an explicit
        # UNKNOWN result without swallowing Module 05 validation failures.
        if unusable or boundary.status in (ModuleStatus.ERROR, ModuleStatus.INVALID_INPUT):
            self.fusion.confirmation.clear_history()
            activity = ActivityEvent(
                f"invalid-{frame.frame_id}", "unknown", frame.frame_id, frame.timestamp_s,
                frame.frame_id, frame.frame_id, frame.timestamp_s, frame.timestamp_s,
                status=ModuleStatus.INVALID_INPUT,
                metadata={"emitted": False, "confirmed": False,
                          "source_id": frame.source_id, "session_id": frame.session_id,
                          "reason": "upstream error/invalid_input"},
            )
        else:
            activity = self.fusion.process(upstream.optimization, boundary)
        timings = dict(upstream.optimization.stage_timings_ms)
        timings.update(boundary_ms=boundary_ms,
                       fusion_ms=activity.metadata.get("processing_time_ms", 0.0),
                       pipeline_ms=(perf_counter() - started) * 1000)
        return MilestoneResult(upstream, boundary, activity, timings)

    def reset(self):
        self.chain.reset()
        self.boundary.reset()
        self.fusion.reset()

    def close(self):
        self.chain.close()

    def __enter__(self):
        try:
            self.initialize()
        except BaseException:
            self.close()
            raise
        return self

    def __exit__(self, *args):
        self.close()
