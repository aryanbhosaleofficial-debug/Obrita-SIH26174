"""Composition boundary. Each stage executes its owner's implementation."""

from dataclasses import dataclass
from threading import RLock

from optimization.pipeline import OptimizationPipeline
from yolo.pipeline import YoloPipeline

from perception.core import FrameProcessor
from shared.config import PipelineConfig
from shared.errors import InitializationError
from shared.schemas.object_frame import ObjectFrame
from shared.schemas.optimization_packet import OptimizationOutputPacket
from shared.schemas.prepared_frame import PreparedFrame


@dataclass
class ChainResult:
    prepared: PreparedFrame
    objects: ObjectFrame
    optimization: OptimizationOutputPacket


class PerceptionChain:
    def __init__(
        self,
        config: PipelineConfig | None = None,
        *,
        detector=None,
        hand_tracker=None,
        pose_tracker=None,
        coordinate_transformer=None,
    ):
        self.config = config or PipelineConfig()
        self.config.validate()
        self.core = FrameProcessor(
            self.config.preprocessing, self.config.stabilization.max_time_gap_s
        )
        self.yolo = YoloPipeline(self.config.detector, detector)
        self.optimization = OptimizationPipeline(
            self.config,
            hand_tracker=hand_tracker,
            pose_tracker=pose_tracker,
            coordinate_transformer=coordinate_transformer,
        )
        self._lock = RLock()
        self._initialized = False
        self._closed = False

    @classmethod
    def from_yaml(cls, path, **backends):
        return cls(PipelineConfig.from_yaml(path), **backends)

    def initialize(self):
        if self._closed:
            raise InitializationError("pipeline is closed; call reset()")
        if self._initialized:
            return
        try:
            self.yolo.initialize()
            self.optimization.initialize()
        except Exception as exc:
            try:
                self.close()
            except Exception as cleanup_error:  # noqa: BLE001 -- retain the original initialization error and report cleanup failure
                exc.add_note(f"cleanup also failed: {cleanup_error}")
            self._closed = False
            if isinstance(exc, InitializationError):
                raise
            raise InitializationError(str(exc)) from exc
        self._initialized = True

    def process(self, packet) -> ChainResult:
        with self._lock:
            if self._closed:
                raise InitializationError("pipeline is closed; call reset()")
            prepared = self.core.process(packet)
            # Invalid input never requires model initialization.
            from shared.enums.module_status import ModuleStatus

            if prepared.status != ModuleStatus.INVALID_INPUT:
                self.initialize()
            objects = self.yolo.process(prepared)
            optimized = self.optimization.process(prepared, objects)
            return ChainResult(prepared, objects, optimized)

    def close(self):
        with self._lock:
            try:
                self.optimization.close()
            finally:
                try:
                    self.yolo.close()
                finally:
                    self._initialized = False
                    self._closed = True

    def reset(self):
        with self._lock:
            self.close()
            self.core.reset()
            self.optimization.reset()
            self._closed = False

    def __enter__(self):
        self.initialize()
        return self

    def __exit__(self, *args):
        self.close()
