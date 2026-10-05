"""Recovered offline boundary processing, adapted to current shared contracts."""

import logging
import math
from collections import deque
from dataclasses import replace
from numbers import Integral, Real

import cv2

from shared.enums.module_status import ModuleStatus
from shared.schemas.boundary_packet import BoundaryOutputPacket
from shared.schemas.frame_packet import FramePacket
from shared.schemas.optimization_packet import OptimizationOutputPacket

from .chain_code.chain_histogram import chain_histogram
from .chain_code.chain_normalizer import normalize_chain_code
from .chain_code.differential_chain import differential_chain_code
from .chain_code.freeman_chain import freeman_chain
from .config import BoundaryConfig
from .features.geometric_features import extract_features
from .features.hand_boundary_features import hand_boundary_interaction
from .input.input_validator import validate_boundary_input, validate_input
from .input.target_selector import select_optimization_target
from .output.boundary_packet_builder import build_packet
from .preprocessing.roi_preprocess import preprocess_roi
from .quality.boundary_quality_gate import evaluate_quality
from .roi.boundary_roi import extract_roi
from .segmentation.foreground_segmenter import candidate_masks
from .segmentation.mask_cleanup import clean_mask
from .segmentation.segmentation_quality import assess_mask, grayscale
from .temporal.boundary_change import BoundaryStateClassifier
from .temporal.boundary_tracker import BoundaryTracker

logger = logging.getLogger(__name__)


class BoundaryPipeline:
    """One ordered stream and one active target per instance; caller serializes calls."""

    def __init__(
        self,
        *,
        config: BoundaryConfig | None = None,
        roi=None,
        tracker=None,
        segmentation_method=None,
        roi_padding=None,
        min_area=None,
        min_component_area=None,
    ):
        self.config = replace(config or BoundaryConfig())
        overrides = {
            "segmentation_method": segmentation_method,
            "roi_padding": roi_padding,
            "min_area": min_area,
            "min_component_area": min_component_area,
        }
        for name, value in overrides.items():
            if value is not None:
                setattr(self.config, name, value)
        self.config.validate()
        self.roi = roi
        self.tracker = (
            tracker
            if tracker is not None
            else BoundaryTracker(
                history=deque(maxlen=self.config.history_frames),
                max_missing_frames=self.config.max_missing_frames,
            )
        )
        self.state_classifier = BoundaryStateClassifier(self.config)
        self.reset()

    @classmethod
    def from_yaml(cls, path):
        return cls(config=BoundaryConfig.from_yaml(path))

    def reset(self):
        self.tracker.reset()
        self.state_classifier.reset()
        self._stream = None
        self._shape = None
        self._target = None
        self._frame_id = None
        self._timestamp = None

    @staticmethod
    def _invalid(frame_id, timestamp, reason, **identity):
        fid = (
            int(frame_id)
            if isinstance(frame_id, Integral)
            and not isinstance(frame_id, bool)
            and frame_id >= 0
            else -1
        )
        ts = (
            float(timestamp)
            if isinstance(timestamp, Real)
            and not isinstance(timestamp, bool)
            and math.isfinite(timestamp)
            and timestamp >= 0
            else 0.0
        )
        return build_packet(
            frame_id=fid,
            timestamp=ts,
            status=ModuleStatus.INVALID_INPUT,
            quality={"quality_ok": False, "confidence": 0.0, "reasons": [reason]},
            **identity,
        )

    def _accept(self, frame_id, timestamp, shape, stream, target=None):
        if self._stream is not None and stream != self._stream:
            return "source/session changed; explicit reset() required"
        if self._shape is not None and shape != self._shape:
            self.reset()
        if (self._frame_id is not None and frame_id <= self._frame_id) or (
            self._timestamp is not None and timestamp <= self._timestamp
        ):
            return "frame_id and timestamp must strictly increase; reset before replay"
        if (
            self._timestamp is not None
            and timestamp - self._timestamp > self.config.max_time_gap_s
        ):
            self.tracker.reset()
            self.state_classifier.reset()
        elif self._frame_id is not None:
            gap = max(0, frame_id - self._frame_id - 1)
            self.tracker.mark_missing(gap)
            if gap > self.config.max_missing_frames:
                self.state_classifier.reset()
        if target is not None and target != self._target:
            self.tracker.reset()
            self.state_classifier.reset()
            self._target = target
        self._stream, self._shape = stream, shape
        self._frame_id, self._timestamp = frame_id, timestamp
        return None

    def _empty(
        self, frame_id, timestamp, reason, status=ModuleStatus.NO_DETECTION, **identity
    ):
        self.tracker.mark_missing()
        self.state_classifier.reset()
        return build_packet(
            frame_id=frame_id,
            timestamp=timestamp,
            status=status,
            quality={"quality_ok": False, "confidence": 0.0, "reasons": [reason]},
            **identity,
        )

    def _analyze(
        self,
        checked,
        selected_roi,
        *,
        rack_valid=False,
        upstream_degraded=False,
        roi_padding=None,
        **identity,
    ):
        config = self.config
        crop = extract_roi(
            checked.frame,
            selected_roi,
            padding=config.roi_padding if roi_padding is None else roi_padding,
        )
        if not crop.valid:
            return self._empty(
                checked.frame_id,
                checked.timestamp,
                crop.reason,
                ModuleStatus.INVALID_INPUT,
                **identity,
            )
        prepared = preprocess_roi(crop.image, grayscale=False, blur=config.blur_kernel)
        gray = grayscale(crop.image)
        if float(gray.std()) < config.min_roi_stddev:
            return self._empty(
                checked.frame_id, checked.timestamp, "low-information ROI", **identity
            )
        candidates = []
        rejected = []
        for polarity, candidate in candidate_masks(
            prepared, config.segmentation_method, **config.segmentation_params
        ):
            mask = clean_mask(
                candidate,
                opening=config.open_kernel,
                closing=config.close_kernel,
                iterations=config.iterations,
                min_component_area=config.min_component_area,
            )
            assessment = assess_mask(mask, gray, config)
            if assessment.contour is not None:
                candidates.append((assessment.score, polarity, mask, assessment))
            else:
                rejected.extend(assessment.reasons)
        if not candidates:
            return self._empty(
                checked.frame_id,
                checked.timestamp,
                "; ".join(sorted(set(rejected))),
                **identity,
            )
        _, polarity, mask, assessment = max(candidates, key=lambda c: c[0])
        logger.debug(
            "frame %s polarity=%s segmentation=%s",
            checked.frame_id,
            polarity,
            assessment.metrics,
        )
        contour = assessment.contour + crop.offset
        chain = freeman_chain(contour)
        if config.normalize_start_point:
            chain = normalize_chain_code(chain)
        differential = (
            normalize_chain_code(differential_chain_code(chain))
            if config.use_differential
            else []
        )
        features = extract_features(contour, chain)
        interaction = hand_boundary_interaction(
            contour,
            checked.hand_data,
            near_threshold=config.contact_distance_px,
        )
        tracking = {
            "tracking_confidence": min(
                assessment.score, self.tracker.history[-1]["confidence"]
            )
            if self.tracker.history
            else 0.0
        }
        quality = evaluate_quality(
            contour=contour,
            features=features,
            mask=mask,
            tracking=tracking,
            segmentation=assessment,
            min_confidence=config.min_confidence,
        )
        if config.require_valid_rack_reference and not rack_valid:
            quality["reasons"].append("valid rack reference required")
        if upstream_degraded:
            quality["reasons"].append("upstream frame or optimization is degraded")
        if quality["reasons"]:
            quality["quality_ok"] = False
            quality["confidence"] = 0.0
        if quality["quality_ok"]:
            tracking = self.tracker.update(
                contour,
                features["centroid"],
                checked.frame_id,
                checked.timestamp,
                assessment.score,
            )
            state, confirmed, count = self.state_classifier.update(
                features["centroid"], interaction, frame_id=checked.frame_id
            )
        else:
            if quality["reasons"] == ["confidence below threshold"]:
                # Valid segmentation may warm geometry continuity under a strict
                # confidence setting, but cannot vote or publish contact/state.
                self.tracker.update(
                    contour,
                    features["centroid"],
                    checked.frame_id,
                    checked.timestamp,
                    assessment.score,
                )
            else:
                self.tracker.mark_missing()
            self.state_classifier.reset()
            state, confirmed, count = None, False, 0
        return build_packet(
            frame_id=checked.frame_id,
            timestamp=checked.timestamp,
            contour=contour,
            chain_code=chain,
            differential_chain_code=differential,
            chain_histogram=chain_histogram(chain),
            features=features,
            interaction=interaction,
            tracking=tracking,
            quality=quality,
            boundary_state=state,
            state_confirmed=confirmed,
            confirmed_frames=count,
            **identity,
        )

    def process(
        self,
        frame,
        frame_id,
        timestamp,
        hand_data=None,
        roi=None,
        *,
        target_track_id=None,
        target_object_track_id=None,
        rack_valid: bool = False,
    ) -> BoundaryOutputPacket:
        """Standalone BGR/grayscale frame. Tuple ROI is XYWH, in source pixels."""
        identity = {
            "target_track_id": target_track_id,
            "target_object_track_id": target_object_track_id,
        }
        checked = validate_input(frame, frame_id, timestamp, hand_data)
        if type(rack_valid) is not bool:
            return self._invalid(
                frame_id, timestamp, "rack_valid must be boolean", **identity
            )
        if not checked.valid:
            return self._invalid(frame_id, timestamp, checked.reason, **identity)
        selected = roi if roi is not None else self.roi
        if selected is None:
            selected = {
                "x": 0,
                "y": 0,
                "width": frame.shape[1],
                "height": frame.shape[0],
            }
        target = (
            ("standalone", target_object_track_id)
            if target_object_track_id is not None
            else ("standalone", str(selected))
        )
        reason = self._accept(
            checked.frame_id, checked.timestamp, frame.shape[:2], "standalone", target
        )
        if reason:
            return self._invalid(frame_id, timestamp, reason, **identity)
        return self._analyze(checked, selected, rack_valid=rack_valid, **identity)

    def process_optimization(
        self,
        packet: OptimizationOutputPacket,
        frame: FramePacket,
        *,
        target_object_track_id=None,
        detection_index=None,
    ) -> BoundaryOutputPacket:
        """Validate the established Module 03 contract; never analyze held boxes."""
        validate_boundary_input(packet, frame)
        identity = {
            "target_track_id": packet.target_track_id,
            "target_object_track_id": target_object_track_id,
        }
        if frame.color_format not in ("BGR", "RGB") or frame.status in (
            ModuleStatus.ERROR,
            ModuleStatus.INVALID_INPUT,
        ):
            return self._invalid(
                frame.frame_id,
                frame.timestamp_s,
                "invalid source frame status/color",
                **identity,
            )
        checked = validate_input(
            frame.image,
            frame.frame_id,
            frame.timestamp_s,
            [
                {
                    "hand_id": h.continuity_key
                    if h.continuity_key is not None
                    else h.hand_id,
                    "landmarks": [(p.x, p.y) for p in h.landmarks],
                }
                for h in packet.spatial.hands
            ],
        )
        if not checked.valid or checked.frame.shape[:2] != (frame.height, frame.width):
            return self._invalid(
                frame.frame_id,
                frame.timestamp_s,
                checked.reason or "image dimensions mismatch",
                **identity,
            )
        reason = self._accept(
            frame.frame_id,
            frame.timestamp_s,
            frame.image.shape[:2],
            (frame.source_id, frame.session_id),
        )
        if reason:
            return self._invalid(frame.frame_id, frame.timestamp_s, reason, **identity)
        if self.config.require_optimization_quality and not packet.quality_ok:
            return self._empty(
                frame.frame_id,
                frame.timestamp_s,
                "optimization quality gate not met",
                **identity,
            )
        index, reason = select_optimization_target(
            packet,
            target_object_track_id=target_object_track_id,
            detection_index=detection_index,
        )
        if index is None:
            return self._empty(frame.frame_id, frame.timestamp_s, reason, **identity)
        detection = packet.object_frame.detections[index]
        target = (frame.source_id, frame.session_id, detection.continuity_key)
        if target != self._target:
            self.tracker.reset()
            self.state_classifier.reset()
            self._target = target
        identity["target_object_track_id"] = detection.track_id
        b = detection.bbox
        padding = self.config.padding_ratio * max(b.x2 - b.x1, b.y2 - b.y1)
        selected = {
            "x": b.x1 - padding,
            "y": b.y1 - padding,
            "width": b.x2 - b.x1 + 2 * padding,
            "height": b.y2 - b.y1 + 2 * padding,
        }
        checked = replace(
            checked,
            frame=cv2.cvtColor(frame.image, cv2.COLOR_RGB2BGR)
            if frame.color_format == "RGB"
            else frame.image,
            hand_data=[
                {
                    "hand_id": h.continuity_key
                    if h.continuity_key is not None
                    else h.hand_id,
                    "landmarks": [(p.x, p.y) for p in h.landmarks],
                }
                for h in packet.spatial.hands
            ],
        )
        checked = validate_input(
            checked.frame, checked.frame_id, checked.timestamp, checked.hand_data
        )
        if not checked.valid:
            return self._invalid(
                frame.frame_id, frame.timestamp_s, checked.reason, **identity
            )
        return self._analyze(
            checked,
            selected,
            rack_valid=packet.spatial.reference_frame.valid,
            upstream_degraded=packet.status == ModuleStatus.DEGRADED
            or frame.status == ModuleStatus.DEGRADED,
            **identity,
        )

    def process_detections(
        self,
        frame,
        frame_id,
        timestamp,
        *,
        person_bbox=None,
        object_bbox=None,
        hand_data=None,
        padding=None,
        target_object_track_id=None,
        rack_valid: bool = False,
    ) -> BoundaryOutputPacket:
        """Compatibility for explicit XYXY object boxes; no detector is invoked."""
        if type(rack_valid) is not bool:
            return self._invalid(frame_id, timestamp, "rack_valid must be boolean")
        if object_bbox is None:
            checked = validate_input(frame, frame_id, timestamp, hand_data)
            if not checked.valid:
                return self._invalid(frame_id, timestamp, checked.reason)
            reason = self._accept(
                checked.frame_id, checked.timestamp, frame.shape[:2], "standalone"
            )
            if reason:
                return self._invalid(frame_id, timestamp, reason)
            return self._empty(frame_id, timestamp, "object_bbox is missing")
        try:
            x1, y1, x2, y2 = object_bbox
            if (
                any(
                    isinstance(v, bool)
                    or not isinstance(v, Real)
                    or not math.isfinite(v)
                    for v in (x1, y1, x2, y2)
                )
                or x2 <= x1
                or y2 <= y1
            ):
                raise ValueError(
                    "object_bbox must have finite coordinates and positive dimensions"
                )
            padding_value = self.config.roi_padding if padding is None else padding
            if type(padding_value) is not int or padding_value < 0:
                raise ValueError("padding must be a nonnegative integer")
            selected = {
                "x": x1 - padding_value,
                "y": y1 - padding_value,
                "width": x2 - x1 + 2 * padding_value,
                "height": y2 - y1 + 2 * padding_value,
            }
        except (ValueError, TypeError):
            return self._invalid(
                frame_id, timestamp, "object_bbox must be XYXY coordinates"
            )
        checked = validate_input(frame, frame_id, timestamp, hand_data)
        if not checked.valid:
            return self._invalid(frame_id, timestamp, checked.reason)
        target = (
            ("standalone", target_object_track_id)
            if target_object_track_id is not None
            else ("standalone", str(selected))
        )
        reason = self._accept(
            checked.frame_id, checked.timestamp, frame.shape[:2], "standalone", target
        )
        if reason:
            return self._invalid(frame_id, timestamp, reason)
        return self._analyze(
            checked,
            selected,
            roi_padding=0,
            rack_valid=rack_valid,
            target_object_track_id=target_object_track_id,
        )


def process(*args, **kwargs):
    """Stateless one-frame convenience; use an instance for temporal continuity."""
    return BoundaryPipeline().process(*args, **kwargs)
