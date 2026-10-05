"""Packet ownership and deterministic reset for the existing spatial wrapper."""

from dataclasses import asdict

import numpy as np
from boundary.input.contract_validator import validate_boundary_input
from optimization.pipeline import OptimizationPipeline

from integration.mocks import MockHandTracker
from perception.core import FrameProcessor
from shared.config import HandTrackerConfig, PipelineConfig
from shared.enums.module_status import ModuleStatus
from shared.schemas.frame_packet import FramePacket
from shared.schemas.observations import HandObservation, Point2D
from shared.schemas.optimization_packet import OptimizationOutputPacket


def test_spatial_packet_uses_canonical_output_and_reset_restarts_backend(
    object_frame, detection
):
    hand = HandObservation("h", None, 0.8, [Point2D(20, 20)], Point2D(20, 20), True)
    tracker = MockHandTracker([[hand], []])
    wrapper = OptimizationPipeline(
        PipelineConfig(hand_tracker=HandTrackerConfig(backend="mock")),
        hand_tracker=tracker,
    )
    core = FrameProcessor()
    frames = [
        FramePacket(i, i / 30, np.zeros((240, 320, 3), np.uint8), 320, 240)
        for i in range(4)
    ]

    def run():
        values = []
        for frame in frames:
            packet = wrapper.process(
                core.process(frame), object_frame(frame.frame_id, [detection()])
            )
            assert type(packet) is OptimizationOutputPacket
            validate_boundary_input(packet, frame)
            assert packet.spatial.hands == packet.observations.hands
            values.append((packet.temporal_window, asdict(packet.spatial)))
        return values

    try:
        first = run()
        wrapper.reset()
        core.reset()
        second = run()
        assert first == second
        assert first[0][1]["hands"]  # Backend script really restarted.
    finally:
        wrapper.close()


def test_geometry_failure_preserves_valid_object_presence(
    monkeypatch, object_frame, detection
):
    import optimization.pipeline as module

    def fail(*args):
        raise ValueError("broken geometry backend")

    monkeypatch.setattr(module, "associate", fail)
    wrapper = OptimizationPipeline(
        PipelineConfig(hand_tracker=HandTrackerConfig(enabled=False, backend="none"))
    )
    frame = FramePacket(0, 0, np.zeros((240, 320, 3), np.uint8), 320, 240)
    try:
        packet = wrapper.process(
            FrameProcessor().process(frame), object_frame(0, [detection()])
        )
        assert packet.status == ModuleStatus.DEGRADED and not packet.interactions
        assert packet.temporal_window[-1].detections[0].observed
        validate_boundary_input(packet, frame)
    finally:
        wrapper.close()
