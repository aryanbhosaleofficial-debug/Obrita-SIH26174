"""Module 01 frame foundation. Legacy combined APIs are lazy compatibility imports."""

from shared.schemas.frame_packet import FramePacket as FramePacket


def __getattr__(name):
    if name == "PerceptionPipeline":
        from integration.legacy import PerceptionPipeline

        return PerceptionPipeline
    if name == "PerceptionConfig":
        from shared.config import PerceptionConfig

        return PerceptionConfig
    if name == "PerceptionFrameResult":
        from shared.schemas.observations import PerceptionFrameResult

        return PerceptionFrameResult
    if name == "FrameProcessor":
        from perception.core import FrameProcessor

        return FrameProcessor
    raise AttributeError(name)
