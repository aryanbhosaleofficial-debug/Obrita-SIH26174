"""Module 03: ObjectFrame + prepared source -> OptimizationOutputPacket.

Relocated perception algorithms; no YOLO ownership or frame-source ownership.
"""

from copy import deepcopy
from dataclasses import replace
from time import perf_counter

import cv2
from optimization.hands.hand_tracker import (
    HandTracker,
    MediaPipeHandTracker,
    NullHandTracker,
    filter_hands,
)
from optimization.interaction.associations import associate
from optimization.interaction.primitives import interaction_candidates
from optimization.pose.pose_tracker import NullPoseTracker, PoseTracker
from optimization.reference_frame.coordinate_frame import (
    ArucoCoordinateTransformer,
    ManualRackTransformer,
    UnavailableReference,
)
from optimization.temporal.stabilizer import PerceptionStabilizer

from shared.config import PipelineConfig
from shared.diagnostics import Diagnostic, NoticeCode, WarningCode
from shared.enums.module_status import ModuleStatus
from shared.geometry import CoordinateTransformer
from shared.schemas.object_frame import ObjectFrame
from shared.schemas.observations import (
    CoordinateFrame,
    OptimizationObservations,
    ReferenceSource,
)
from shared.schemas.optimization_packet import OptimizationOutputPacket
from shared.schemas.prepared_frame import PreparedFrame
from shared.schemas.spatial_feature_packet import Landmark, SpatialFeaturePacket
from shared.utils.observation import valid_point, valid_score


class OptimizationPipeline:
    def __init__(
        self,
        config: PipelineConfig,
        *,
        hand_tracker: HandTracker | None = None,
        pose_tracker: PoseTracker | None = None,
        coordinate_transformer: CoordinateTransformer | None = None,
    ):
        config.validate()
        self.config = config
        h, r = config.hand_tracker, config.reference_frame
        if hand_tracker is not None:
            self.hand_tracker = hand_tracker
        elif not h.enabled or h.backend == "none":
            self.hand_tracker = NullHandTracker()
        elif h.backend == "mediapipe":
            self.hand_tracker = MediaPipeHandTracker(h)
        else:
            from integration.mocks import MockHandTracker

            self.hand_tracker = MockHandTracker()
        self.pose_tracker = (
            pose_tracker if pose_tracker is not None else NullPoseTracker()
        )
        self.coordinate_transformer = (
            coordinate_transformer
            if coordinate_transformer is not None
            else (
                UnavailableReference()
                if not r.enabled
                else ArucoCoordinateTransformer(
                    r.marker_ids, r.aruco_dictionary, r.reference_id
                )
                if r.type == "aruco"
                else ManualRackTransformer(r.corners_normalized or [], r.reference_id)
            )
        )
        self._stabilizer = PerceptionStabilizer(
            config.stabilization, config.interaction
        )
        self._reference_context = None
        self._initialized = False

    def initialize(self):
        if not self._initialized:
            self.hand_tracker.initialize()
            self.pose_tracker.initialize()
            self._initialized = True

    def close(self):
        try:
            self.pose_tracker.close()
        finally:
            try:
                self.hand_tracker.close()
            finally:
                self._initialized = False

    def reset(self):
        self._stabilizer.reset()
        self._reference_context = None

    def process(
        self, prepared: PreparedFrame, objects: ObjectFrame
    ) -> OptimizationOutputPacket:
        started = perf_counter()
        source = prepared.source
        if source is None:
            raise ValueError("PreparedFrame must retain source")
        if (
            objects.frame_id,
            objects.timestamp_s,
            objects.source_id,
            objects.session_id,
            objects.image_width,
            objects.image_height,
        ) != (
            source.frame_id,
            source.timestamp_s,
            source.source_id,
            source.session_id,
            source.width,
            source.height,
        ):
            raise ValueError("ObjectFrame metadata does not match PreparedFrame source")
        result = OptimizationObservations(
            source.frame_id,
            source.timestamp_s,
            source.source_id,
            image_width=source.width,
            image_height=source.height,
            session_id=source.session_id,
        )
        result.stage_timings_ms = {
            name: 0.0
            for name in (
                "preprocessing_ms",
                "object_detection_ms",
                "hand_tracking_ms",
                "pose_tracking_ms",
                "coordinate_transform_ms",
                "association_ms",
                "stabilization_ms",
            )
        }
        result.stage_timings_ms.update(prepared.stage_timings_ms)
        result.stage_timings_ms.update(objects.stage_timings_ms)
        result.warnings = list(prepared.warnings) + [
            w for w in objects.warnings if w not in prepared.warnings
        ]
        result.notices = list(objects.notices)

        def timed(name, action):
            t = perf_counter()
            try:
                return action()
            finally:
                result.stage_timings_ms[name] += (perf_counter() - t) * 1000

        def finish():
            result.processing_time_ms = (
                (perf_counter() - started) * 1000
                + prepared.stage_timings_ms.get("preprocessing_ms", 0)
                + objects.stage_timings_ms.get("object_detection_ms", 0)
            )
            result.stage_timings_ms["total_ms"] = result.processing_time_ms
            # Health + stable current evidence, not a claim of verified touch or identity.
            result.reliable_for_temporal_reasoning = result.status in (
                ModuleStatus.OK,
                ModuleStatus.NO_DETECTION,
            ) and any(d.is_stable for d in result.detections)
            spatial = SpatialFeaturePacket(
                source.frame_id,
                source.timestamp_s,
                hands=result.hands,
                status=result.status,
                reference_frame=result.reference_frame,
            )
            # SpatialFeaturePacket describes one operator; the complete injected
            # pose list remains observable in observations.poses.
            if result.poses:
                pose = result.poses[0]
                spatial.pose_landmarks = [Landmark(p.x, p.y) for p in pose.landmarks]
                spatial.rack_relative_pose = [
                    (p.x, p.y, None) for p in (pose.reference_landmarks or [])
                ]
            return OptimizationOutputPacket(
                source.frame_id,
                source.timestamp_s,
                object_frame=replace(objects, detections=result.detections),
                spatial=spatial,
                interactions=result.interactions,
                quality_ok=result.reliable_for_temporal_reasoning,
                quality_reasons=[w.code.value for w in result.warnings],
                status=result.status,
                observations=result,
                source_id=source.source_id,
                session_id=source.session_id,
                reliable_for_temporal_reasoning=result.reliable_for_temporal_reasoning,
                warnings=result.warnings,
                notices=result.notices,
                stage_timings_ms=result.stage_timings_ms,
            )

        if prepared.status == ModuleStatus.INVALID_INPUT:
            if prepared.accepted:
                self._stabilizer.age_missing(prepared.missing_frames)
            result.status = ModuleStatus.INVALID_INPUT
            return finish()
        if prepared.reset_required:
            self.close()
            self.reset()
        elif prepared.missing_frames:
            self._stabilizer.age_missing(prepared.missing_frames)
        self.initialize()
        result.detections = deepcopy(objects.detections)
        shape = (source.height, source.width)
        hand_failed = False
        try:

            def hands():
                raw = self.hand_tracker.track(
                    prepared.image, timestamp_s=source.timestamp_s
                )
                return filter_hands([prepared.source_hand(h) for h in raw])

            result.hands, invalid = timed("hand_tracking_ms", hands)
            if invalid:
                result.warnings.append(
                    Diagnostic(
                        WarningCode.INVALID_OBSERVATION,
                        {"stage": "hands", "count": invalid},
                    )
                )
        except Exception as exc:  # noqa: BLE001 -- isolate replaceable backend failure as structured runtime diagnostics
            hand_failed = True
            result.warnings.append(
                Diagnostic(WarningCode.HAND_TRACKER_FAILURE, {"message": str(exc)})
            )
        try:

            def poses():
                raw = self.pose_tracker.track(prepared.image)
                output = [prepared.source_pose(p) for p in raw]
                if any(
                    not valid_score(p.confidence)
                    or not all(valid_point(pt) for pt in p.landmarks)
                    for p in output
                ):
                    raise ValueError("invalid pose observation")
                return output

            result.poses = timed("pose_tracking_ms", poses)
        except Exception as exc:  # noqa: BLE001 -- isolate replaceable backend failure as structured runtime diagnostics
            result.warnings.append(
                Diagnostic(WarningCode.POSE_TRACKER_FAILURE, {"message": str(exc)})
            )

        def transform():
            bgr = (
                cv2.cvtColor(source.image, cv2.COLOR_RGB2BGR)
                if source.color_format == "RGB"
                else source.image
            )
            info = self.coordinate_transformer.update(bgr)
            if not info.valid:
                return info
            if not info.reference_id:
                raise ValueError("valid reference requires reference_id")

            def convert(point):
                mapped = self.coordinate_transformer.image_to_reference(point, shape)
                if not valid_point(mapped):
                    raise ValueError("nonfinite reference coordinates")
                return mapped

            for d in result.detections:
                d.reference_polygon = tuple(convert(p) for p in d.bbox.corners)
            for h in result.hands:
                h.reference_landmarks = [convert(p) for p in h.landmarks]
                h.reference_palm_center = convert(h.palm_center)
            for p in result.poses:
                p.reference_landmarks = [convert(pt) for pt in p.landmarks]
            if info.verified_this_frame:
                info.verified_timestamp_s = source.timestamp_s
            return info

        try:
            result.reference_frame = timed("coordinate_transform_ms", transform)
            result.coordinate_frame_valid = result.reference_frame.valid
        except Exception as exc:  # noqa: BLE001 -- isolate replaceable backend failure as structured runtime diagnostics
            result.warnings.append(
                Diagnostic(WarningCode.REFERENCE_FRAME_FAILURE, {"message": str(exc)})
            )
        if not result.coordinate_frame_valid:
            for d in result.detections:
                d.reference_polygon = None
            for h in result.hands:
                h.reference_landmarks = h.reference_palm_center = None
            for p in result.poses:
                p.reference_landmarks = None
            if self.config.reference_frame.enabled or not isinstance(
                self.coordinate_transformer, UnavailableReference
            ):
                result.warnings.append(
                    Diagnostic(WarningCode.REFERENCE_FRAME_UNAVAILABLE)
                )
            else:
                result.notices.append(Diagnostic(NoticeCode.REFERENCE_DISABLED))
        elif result.reference_frame.source == ReferenceSource.STATIC_MANUAL:
            result.notices.append(Diagnostic(NoticeCode.STATIC_REFERENCE))
        result.association_coordinate_frame = (
            CoordinateFrame.RACK_RELATIVE
            if result.coordinate_frame_valid
            else CoordinateFrame.IMAGE_DIAGONAL
        )
        context = (result.coordinate_frame_valid, result.reference_frame.reference_id)
        if context != self._reference_context:
            self._stabilizer.reset_geometry()
            self._reference_context = context
        try:
            timed(
                "stabilization_ms",
                lambda: self._stabilizer.update_observations(
                    result.detections,
                    result.hands,
                    shape,
                    source.timestamp_s,
                    result.coordinate_frame_valid,
                ),
            )
            result.associations = timed(
                "association_ms",
                lambda: associate(
                    result.hands,
                    result.detections,
                    shape,
                    self.config.interaction,
                    result.coordinate_frame_valid,
                ),
            )

            def stabilize():
                self._stabilizer.update_trends(result.associations, source.timestamp_s)
                candidates = interaction_candidates(
                    result.detections, result.hands, result.associations
                )
                return self._stabilizer.update_interactions(
                    candidates, result.detections
                )

            result.interactions = timed("stabilization_ms", stabilize)
        except Exception as exc:  # noqa: BLE001 -- isolate replaceable backend failure as structured runtime diagnostics
            result.associations, result.interactions = [], []
            self._stabilizer.age_missing(1)
            result.warnings.append(
                Diagnostic(WarningCode.GEOMETRY_FAILURE, {"message": str(exc)})
            )
        if any(h.confidence is None for h in result.hands):
            result.notices.append(Diagnostic(NoticeCode.HAND_CONFIDENCE_UNAVAILABLE))
        if (
            not self.config.hand_tracker.enabled
            or self.config.hand_tracker.backend == "none"
        ):
            result.notices.append(Diagnostic(NoticeCode.HAND_TRACKER_DISABLED))
        if any(not h.identity_persistent for h in result.hands):
            result.notices.append(Diagnostic(NoticeCode.HAND_IDENTITY_NONPERSISTENT))
        if any(a.ambiguous for a in result.associations):
            result.notices.append(Diagnostic(NoticeCode.AMBIGUOUS_ASSOCIATION))
        result.status = ModuleStatus.DEGRADED if result.warnings else ModuleStatus.OK
        if (
            not result.detections
            and not result.hands
            and not result.poses
            and not result.warnings
        ):
            result.status = ModuleStatus.NO_DETECTION
        if objects.status == ModuleStatus.ERROR and (
            hand_failed
            or not self.config.hand_tracker.enabled
            or self.config.hand_tracker.backend == "none"
        ):
            result.status = ModuleStatus.ERROR
        return finish()
