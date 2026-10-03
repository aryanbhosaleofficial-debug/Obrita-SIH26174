"""End-to-End Integrated Pipeline for ORBITA Human Activity Recognition."""

from typing import Any, Dict, List, Optional, Tuple
import numpy as np
import torch

from ..schemas.spatial_types import PersonPose3D
from ..schemas.tracking_types import TrackingResult
from ..schemas.dataset_types import PredictionResult
from ..spatial.coordinate_systems import CoordinateFrameManager
from ..features.temporal_features import TemporalFeatureBuilder, TemporalSequenceManager
from ..tracking.tracker import MultiPersonTracker
from ..models.bottleneck_network import OrbitaBottleneckHAR
from .pose_adapter import MediaPipePoseLandmarkerRunner
from .serialization import DataLogger
from .visualizer import TrajectoryVisualizer3D


CLASS_NAMES = [
    "IDLE_MONITORING",
    "RACK_INSPECTION",
    "SWITCH_ACTUATION",
    "CABLE_ROUTING",
    "EQUIPMENT_MAINTENANCE",
    "EMERGENCY_SHUTDOWN"
]


class OrbitaHARPipeline:
    """Master pipeline integrating all 4 tasks into an on-board activity recognition system."""

    def __init__(
        self,
        pose_runner: Optional[MediaPipePoseLandmarkerRunner] = None,
        model: Optional[OrbitaBottleneckHAR] = None,
        logger: Optional[DataLogger] = None,
        sequence_length: int = 30,
        enable_logging: bool = True
    ):
        self.pose_runner = pose_runner or MediaPipePoseLandmarkerRunner()
        self.tracker = MultiPersonTracker(max_persons=2)
        self.feat_builder = TemporalFeatureBuilder(sequence_length=sequence_length)
        self.seq_manager = TemporalSequenceManager(sequence_length=sequence_length, step_size=10)
        self.model = model or OrbitaBottleneckHAR(input_dim=74, sequence_length=sequence_length)
        self.model.eval()
        self.logger = logger or DataLogger() if enable_logging else None
        self.visualizer = TrajectoryVisualizer3D(enable_gui=False)
        self.frame_counter = 0

    def process_frame(
        self,
        image_rgb: Optional[np.ndarray],
        timestamp_ms: int
    ) -> Tuple[TrackingResult, List[PredictionResult]]:
        """Processes one video/camera frame through the full pipeline."""
        self.frame_counter += 1

        # 1. Pose Landmark Detection (Task 1)
        raw_detections = self.pose_runner.detect_frame(
            image_rgb=image_rgb,
            timestamp_ms=timestamp_ms,
            frame_index=self.frame_counter
        )

        # 2. Multi-Person Association (Task 3: Human 1 and Human 2)
        tracking_result = self.tracker.update(raw_detections, timestamp_ms)

        # Forward the same person-specific tracked 3D poses to the visualization
        # interface. Visualization failures must not stop offline inference when
        # Matplotlib is unavailable.
        try:
            self.visualizer.render_tracks(tracking_result.active_tracks)
        except RuntimeError:
            pass

        predictions: List[PredictionResult] = []

        # 3. Process Each Tracked Person (Human 1 / Human 2)
        for slot_id, tracked_person in tracking_result.active_tracks.items():
            if tracked_person.last_pose is None:
                continue
            # A coasting track exposes uncertainty but must not create a fresh
            # feature/sequence sample from its stale last observation.
            if tracked_person.last_observed_timestamp_ms != timestamp_ms:
                continue

            pose_3d = tracked_person.last_pose

            # 4. Feature Extraction (Task 2)
            frame_feat = self.feat_builder.extract_frame_features(pose_3d)

            # Log frame features
            if self.logger is not None:
                self.logger.log_frame_feature(frame_feat)

            # 5. Temporal Sequence Windowing (Task 2 & 4)
            sample = self.seq_manager.add_frame_feature(frame_feat)

            # 6. Bottleneck Model Inference (Task 4)
            if sample is not None:
                if sample.feature_schema_version != self.model.feature_schema_version:
                    raise ValueError(
                        "Task 2 feature schema is incompatible with the Task 4 model"
                    )
                if sample.feature_dim != self.model.input_dim:
                    raise ValueError(
                        f"Task 2 feature dimension {sample.feature_dim} does not match "
                        f"Task 4 input dimension {self.model.input_dim}"
                    )
                x_tensor = torch.from_numpy(sample.features).float().unsqueeze(0) # (1, T, D)
                m_tensor = torch.from_numpy(sample.missingness_mask).float().unsqueeze(0)

                with torch.no_grad():
                    logits, _ = self.model(x_tensor, m_tensor)
                    probs = torch.softmax(logits, dim=-1)[0].cpu().numpy()

                pred_id = int(np.argmax(probs))
                pred_name = CLASS_NAMES[pred_id]
                conf = float(probs[pred_id])

                pred_result = PredictionResult(
                    timestamp_ms=timestamp_ms,
                    person_id=slot_id,
                    predicted_class_id=pred_id,
                    predicted_class_name=pred_name,
                    confidence=conf,
                    probabilities={CLASS_NAMES[i]: float(probs[i]) for i in range(len(CLASS_NAMES))},
                    is_reliable=(tracked_person.hits >= 3 and conf >= 0.35),
                    notes="Nominal inference"
                )
                predictions.append(pred_result)

                # Log predictions
                if self.logger is not None:
                    self.logger.log_prediction(pred_result)

        return tracking_result, predictions

    def run_smoke_pipeline(self, num_frames: int = 40) -> Dict:
        """Executes full pipeline on synthetic frames to verify integrated execution."""
        all_predictions = []
        for i in range(num_frames):
            t_ms = i * 33 # 30 fps
            tracking_res, preds = self.process_frame(image_rgb=None, timestamp_ms=t_ms)
            all_predictions.extend(preds)

        return {
            "status": "SUCCESS",
            "frames_processed": num_frames,
            "predictions_count": len(all_predictions),
            "sample_prediction": all_predictions[-1].to_dict() if all_predictions else None
        }

    def run_video(
        self,
        source: Any = 0,
        max_frames: Optional[int] = None,
        display: bool = False
    ) -> Dict:
        """Processes live camera feed (source=int) or video file (source=str).
        
        Prerequisites:
        1. MediaPipe Pose Landmarker model asset: models/pose_landmarker.task
        2. Operational camera device or readable video container.
        """
        import cv2

        cap = cv2.VideoCapture(source)
        if not cap.isOpened():
            return {
                "status": "FAILED",
                "error": f"Cannot open video source: {source}",
                "frames_processed": 0
            }

        frames_processed = 0
        all_predictions = []

        try:
            while True:
                if max_frames and frames_processed >= max_frames:
                    break

                ret, frame_bgr = cap.read()
                if not ret:
                    break

                frames_processed += 1
                timestamp_ms = int(cap.get(cv2.CAP_PROP_POS_MSEC))
                if timestamp_ms == 0:
                    timestamp_ms = int(frames_processed * 33.3)

                frame_rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
                tracking_res, preds = self.process_frame(image_rgb=frame_rgb, timestamp_ms=timestamp_ms)
                all_predictions.extend(preds)

                if display:
                    # Overlay tracking status
                    for slot, track in tracking_res.active_tracks.items():
                        if track.last_centroid_2d is not None:
                            h, w = frame_bgr.shape[:2]
                            cx, cy = int(track.last_centroid_2d[0] * w), int(track.last_centroid_2d[1] * h)
                            cv2.putText(frame_bgr, f"{slot}:{track.state.value}", (cx, cy),
                                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)
                    cv2.imshow("ORBITA Live Activity Recognition", frame_bgr)
                    if cv2.waitKey(1) & 0xFF == 27: # ESC to stop
                        break
        finally:
            cap.release()
            if display:
                cv2.destroyAllWindows()

        return {
            "status": "SUCCESS",
            "frames_processed": frames_processed,
            "predictions_count": len(all_predictions)
        }
