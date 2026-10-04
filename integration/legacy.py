"""Deprecated combined API. New consumers use FrameProcessor and real stage packets."""

from integration.chain import PerceptionChain


class PerceptionPipeline(PerceptionChain):
    """Compatibility wrapper only; there is no parallel processing implementation."""

    def process(self, packet):
        return super().process(packet).optimization.observations

    @property
    def coordinate_transformer(self):
        return self.optimization.coordinate_transformer

    @property
    def detector(self):
        return self.yolo.detector

    @property
    def hand_tracker(self):
        return self.optimization.hand_tracker
