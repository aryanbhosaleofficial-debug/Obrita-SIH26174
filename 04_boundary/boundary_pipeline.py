"""Independent, deterministic boundary pipeline for one image frame."""
from __future__ import annotations

from .input.input_validator import validate_input
from .roi.boundary_roi import extract_roi
from .preprocessing.roi_preprocess import preprocess_roi
from .segmentation.foreground_segmenter import segment
from .segmentation.mask_cleanup import clean_mask
from .contour.contour_extractor import extract_contours
from .contour.contour_validator import select_best_contour
from .chain_code.freeman_chain import freeman_chain
from .chain_code.chain_normalizer import normalize_chain_code
from .chain_code.differential_chain import differential_chain_code
from .chain_code.chain_histogram import chain_histogram
from .features.geometric_features import extract_features
from .features.hand_boundary_features import hand_boundary_interaction
from .temporal.boundary_tracker import BoundaryTracker
from .quality.boundary_quality_gate import evaluate_quality
from .output.boundary_packet_builder import build_packet


class BoundaryPipeline:
    def __init__(self, *, roi=None, tracker=None, segmentation_method="threshold", roi_padding=0, min_area=20, min_component_area=0):
        self.roi = roi; self.tracker = tracker or BoundaryTracker(); self.segmentation_method = segmentation_method; self.roi_padding = roi_padding; self.min_area = min_area; self.min_component_area = min_component_area

    def process(self, frame, frame_id, timestamp, hand_data=None, roi=None):
        checked = validate_input(frame, frame_id, timestamp, hand_data)
        if not checked.valid: return build_packet(frame_id=frame_id if isinstance(frame_id, int) else -1, timestamp=float(timestamp) if isinstance(timestamp, (int, float)) else 0.0, quality={"status": "INVALID", "quality_ok": False, "confidence": 0.0, "reasons": [checked.reason]})
        selected_roi = roi or self.roi or {"x": 0, "y": 0, "width": checked.frame.shape[1], "height": checked.frame.shape[0]}
        crop = extract_roi(checked.frame, selected_roi, padding=self.roi_padding)
        if not crop.valid: return build_packet(frame_id=checked.frame_id, timestamp=checked.timestamp, quality={"status": "INVALID", "quality_ok": False, "confidence": 0.0, "reasons": [crop.reason]})
        prepared = preprocess_roi(crop.image, grayscale=False, blur=3)
        mask = clean_mask(segment(prepared, self.segmentation_method), min_component_area=self.min_component_area)
        contours = extract_contours(mask, crop.offset); contour, _, reason = select_best_contour(contours, min_area=self.min_area)
        if contour is None: return build_packet(frame_id=checked.frame_id, timestamp=checked.timestamp, interaction=hand_boundary_interaction(None, hand_data), quality={"status": "NO_BOUNDARY", "quality_ok": False, "confidence": 0.0, "reasons": [reason]})
        chain = normalize_chain_code(freeman_chain(contour)); features = extract_features(contour, chain); interaction = hand_boundary_interaction(contour, hand_data); tracking = self.tracker.update(contour, features["centroid"], checked.frame_id, checked.timestamp, 0.9); quality = evaluate_quality(contour=contour, features=features, mask=mask, tracking=tracking)
        return build_packet(frame_id=checked.frame_id, timestamp=checked.timestamp, contour=contour, chain_code=chain, differential_chain_code=differential_chain_code(chain), chain_histogram=chain_histogram(chain), features=features, interaction=interaction, tracking=tracking, quality=quality)

    def process_detections(self, frame, frame_id, timestamp, *, person_bbox=None,
                           object_bbox=None, hand_data=None, padding=None):
        """Process a YOLO-selected object without running detection in Module 04.

        ``person_bbox`` is retained as upstream context. ``object_bbox`` defines
        the target-specific ROI; when it is absent the result is an explicit
        no-boundary packet rather than a full-frame guess.
        """
        if object_bbox is None:
            return build_packet(frame_id=frame_id, timestamp=timestamp,
                                quality={"status": "NO_BOUNDARY", "quality_ok": False,
                                         "confidence": 0.0,
                                         "reasons": ["YOLO object_bbox is missing"]})
        result = self.process(frame, frame_id, timestamp, hand_data=hand_data,
                              roi=object_bbox)
        # Keep upstream association metadata available for Module 05 adapters.
        if hasattr(result, "target_object_track_id"):
            result.target_object_track_id = getattr(result, "target_object_track_id", None)
            result.metadata = {"person_bbox": person_bbox, "object_bbox": object_bbox}
        elif isinstance(result, dict):
            result["detection_context"] = {"person_bbox": person_bbox, "object_bbox": object_bbox}
        return result


process = BoundaryPipeline().process
