"""Offline Module 05 baseline: paired shared packets -> shared ActivityEvent."""
from time import perf_counter
from fusion.config import load_config, validate_config
from fusion.input.packet_validator import validate_packets
from fusion.input.fusion_synchronizer import synchronize
from fusion.evidence import object_evidence, gesture_evidence, interaction_evidence, motion_evidence, contact_evidence, boundary_evidence
from fusion.fusion.evidence_fusion import candidates
from fusion.fusion.conflict_resolver import resolve
from fusion.har.activity_recognizer import recognize
from fusion.har.activity_event_builder import build
from fusion.temporal.activity_confirmation import ActivityConfirmation


class FusionPipeline:
    def __init__(self, config=None):
        self.config = validate_config(config) if config is not None else load_config()
        self.confirmation = ActivityConfirmation(self.config["temporal"])
        self.reset()

    @classmethod
    def from_yaml(cls, path):
        return cls(load_config(path))

    def reset(self):
        self.confirmation.reset()
        self._stream = self._last_id = self._last_time = None

    def process(self, optimization_output, boundary_output=None):
        started = perf_counter()
        packet, boundary = optimization_output, boundary_output
        try:
            validate_packets(packet, boundary)
            synchronize(packet, boundary, self.config["input"])
            stream = (packet.source_id, packet.session_id)
            if self._stream is not None and stream != self._stream:
                raise ValueError("fusion source/session changed; explicit reset required")
            if self._last_id is not None and (packet.frame_id <= self._last_id or packet.timestamp_s <= self._last_time):
                raise ValueError("fusion frame_id/timestamp must strictly increase")
        except (TypeError, ValueError):
            self.confirmation.clear_history()
            raise
        if self._last_time is not None and packet.timestamp_s - self._last_time > self.config["temporal"]["max_time_gap_s"]:
            self.confirmation.clear_history()
        self._stream, self._last_id, self._last_time = stream, packet.frame_id, packet.timestamp_s
        index, detection = object_evidence.target(packet, boundary)
        raw = {
            "object": object_evidence.extract(detection),
            "gesture": gesture_evidence.extract(packet),
            "interaction": interaction_evidence.extract(packet, index, self.config["evidence"]["interaction_priority"]),
            "motion": motion_evidence.extract(packet, detection, self.config["evidence"]["motion_min_speed"]),
            "contact": contact_evidence.extract(boundary),
            "boundary": boundary_evidence.extract(boundary),
        }
        evidence = {s: item for s, item in raw.items() if item is not None and item[1] >= self.config["evidence"]["min_confidence"][s]} if detection else {}
        evidence, conflicts = resolve(evidence, boundary, self.config["conflict_resolution"])
        candidate = recognize(candidates(evidence, self.config))
        object_key = (detection.continuity_key, detection.track_id, detection.class_name) if detection else None
        key = (stream, packet.target_track_id, object_key) if detection else self.confirmation.key
        confirmed, emitted, start, event_id = self.confirmation.update(key, packet.frame_id, packet.timestamp_s, candidate[0])
        result = build(packet, detection, candidate, confirmed, emitted, start, event_id, conflicts, evidence)
        result.metadata["processing_time_ms"] = (perf_counter() - started) * 1000
        return result
