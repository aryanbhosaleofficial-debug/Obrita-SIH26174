"""Authoritative Module 01: validate/prepare a frame, never run model inference."""

import math
from dataclasses import replace
from numbers import Integral, Real
from pathlib import Path
from threading import RLock
from time import perf_counter

import cv2
import numpy as np
import yaml

from perception.preprocessing import preprocess
from shared.config import ConfigurationError, PerceptionConfig, PreprocessingConfig
from shared.diagnostics import Diagnostic, WarningCode
from shared.enums.module_status import ModuleStatus
from shared.schemas.frame_packet import FramePacket
from shared.schemas.prepared_frame import PreparedFrame


class FrameProcessor:
    """One ordered source/session; invalid frames age consumers, resets are explicit."""

    def __init__(
        self, config: PreprocessingConfig | None = None, max_time_gap_s: float = 1.0
    ):
        self.config = config or PreprocessingConfig()
        PerceptionConfig(preprocessing=self.config).validate()
        if (
            isinstance(max_time_gap_s, bool)
            or not isinstance(max_time_gap_s, Real)
            or not math.isfinite(max_time_gap_s)
            or max_time_gap_s <= 0
        ):
            raise ConfigurationError("max_time_gap_s must be finite and positive")
        self.max_time_gap_s: float = float(max_time_gap_s)
        self._lock: RLock = RLock()
        self.reset()

    @classmethod
    def from_yaml(cls, path: str | Path):
        data = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
        if not isinstance(data, dict) or set(data) != {"perception"}:
            raise ConfigurationError("expected perception configuration")
        section = data["perception"]
        if not isinstance(section, dict) or set(section) - {"preprocessing"}:
            raise ConfigurationError("Module 01 accepts preprocessing settings only")
        try:
            return cls(PreprocessingConfig(**section.get("preprocessing", {})))
        except TypeError as exc:
            raise ConfigurationError(str(exc)) from exc

    def reset(self) -> None:
        with self._lock:
            self._identity: tuple[str, str] | None = None
            self._last_id: int | None = None
            self._timestamp: float | None = None
            self._last_valid_timestamp: float | None = None
            self._shape: tuple[int, int] | None = None

    def process(self, packet: FramePacket) -> PreparedFrame:
        with self._lock:
            started = perf_counter()
            valid_id = (
                isinstance(packet.frame_id, Integral)
                and not isinstance(packet.frame_id, (bool, np.bool_))
                and packet.frame_id >= 0
            )
            valid_time = (
                isinstance(packet.timestamp_s, Real)
                and not isinstance(packet.timestamp_s, (bool, np.bool_))
                and math.isfinite(packet.timestamp_s)
            )
            if valid_id:
                packet = replace(packet, frame_id=int(packet.frame_id))
            if valid_time:
                packet = replace(packet, timestamp_s=float(packet.timestamp_s))
            result = PreparedFrame(np.empty((0, 0, 3), np.uint8), 1.0, 1.0, packet)

            def finish():
                result.stage_timings_ms["preprocessing_ms"] = (
                    perf_counter() - started
                ) * 1000
                return result

            identity = (packet.source_id, packet.session_id)
            if self._identity is not None and identity != self._identity:
                result.status = ModuleStatus.INVALID_INPUT
                result.accepted = False
                result.warnings.append(
                    Diagnostic(
                        WarningCode.SOURCE_CHANGED,
                        {"action": "reset before changing source/session"},
                    )
                )
                return finish()
            if (
                valid_id
                and self._last_id is not None
                and packet.frame_id <= self._last_id
            ) or (
                valid_time
                and self._timestamp is not None
                and packet.timestamp_s <= self._timestamp
            ):
                result.status = ModuleStatus.INVALID_INPUT
                result.accepted = False
                result.warnings.append(Diagnostic(WarningCode.NON_MONOTONIC_FRAME))
                return finish()
            gap = (
                max(0, int(packet.frame_id) - self._last_id - 1)
                if valid_id and self._last_id is not None
                else 0
            )
            try:
                drops = packet.dropped_frames_before
                if (
                    isinstance(drops, (bool, np.bool_))
                    or not isinstance(drops, Integral)
                    or drops < 0
                ):
                    raise ValueError(
                        "dropped_frames_before must be a nonnegative integer"
                    )
                # Capture may use consecutive IDs even when frames were dropped.
                # A reported count and an ID gap describe the same missing span.
                gap = max(gap, int(drops))
                if not valid_id or not valid_time:
                    raise ValueError("frame identity/time must be valid")
                if not isinstance(packet.session_id, str) or not packet.session_id:
                    raise ValueError("session_id must be nonempty")
                if packet.status in (ModuleStatus.ERROR, ModuleStatus.INVALID_INPUT):
                    raise ValueError("upstream frame invalid")
                result = preprocess(packet, self.config)
                if packet.status == ModuleStatus.DEGRADED:
                    result.warnings.append(
                        Diagnostic(WarningCode.UPSTREAM_FAILURE, {"stage": "source"})
                    )
                result.missing_frames = gap
                shape = (packet.height, packet.width)
                result.reset_required = self._shape is not None and (
                    self._shape != shape
                    or self._last_valid_timestamp is None
                    or packet.timestamp_s - self._last_valid_timestamp
                    > self.max_time_gap_s
                )
                self._shape = shape
                self._last_valid_timestamp = packet.timestamp_s
                if gap:
                    result.warnings.append(
                        Diagnostic(WarningCode.SOURCE_FRAME_MISSING, {"count": gap})
                    )
                if result.reset_required:
                    result.warnings.append(
                        Diagnostic(WarningCode.TEMPORAL_HISTORY_RESET)
                    )
                result.status = (
                    ModuleStatus.DEGRADED if result.warnings else ModuleStatus.OK
                )
            except (ValueError, TypeError, OverflowError, cv2.error) as exc:
                result.status = ModuleStatus.INVALID_INPUT
                result.missing_frames = gap + 1
                result.warnings.append(
                    Diagnostic(WarningCode.INVALID_FRAME, {"reason": str(exc)})
                )
            if valid_id:
                self._last_id = packet.frame_id
            if valid_time:
                self._timestamp = packet.timestamp_s
            if isinstance(packet.source_id, str) and packet.source_id:
                self._identity = identity
            return finish()
