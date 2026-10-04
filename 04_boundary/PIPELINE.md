# Module 04 — Boundary Detection Pipeline

## Overview

```text
  PREVIOUS: 03 Optimization (OptimizationOutputPacket) + 01 Perception Core (FramePacket via buffer)
                                     │
                                     ▼
              ┌────────────────────────────────────┐
              │ 1. Synchronization                 │  input/input_synchronizer.py
              └─────────────────┬──────────────────┘
                                ▼
              ┌────────────────────────────────────┐
              │ 2. Input Validation                │  input/input_validator.py
              └─────────────────┬──────────────────┘
                                ▼
              ┌────────────────────────────────────┐
              │ 3. Target Selection                │  input/target_selector.py
              └─────────────────┬──────────────────┘
                                ▼
              ┌────────────────────────────────────┐
              │ 4. Boundary ROI                    │  roi/boundary_roi.py
              └─────────────────┬──────────────────┘
                                ▼
              ┌────────────────────────────────────┐
              │ 5. ROI Preprocessing               │  preprocessing/roi_preprocess.py,
              │                                    │  preprocessing/illumination.py
              └─────────────────┬──────────────────┘
                                ▼
              ┌────────────────────────────────────┐
              │ 6. Segmentation                    │  segmentation/foreground_segmenter.py,
              │                                    │  segmentation/hsv_segmenter.py
              └─────────────────┬──────────────────┘
                                ▼
              ┌────────────────────────────────────┐
              │ 7. Mask Cleanup                    │  segmentation/mask_cleanup.py
              └─────────────────┬──────────────────┘
                                ▼
              ┌────────────────────────────────────┐
              │ 8. Contour Extraction              │  contour/contour_extractor.py
              └─────────────────┬──────────────────┘
                                ▼
              ┌────────────────────────────────────┐
              │ 9. Contour Association             │  contour/contour_association.py
              └─────────────────┬──────────────────┘
                                ▼
              ┌────────────────────────────────────┐
              │ 10. Contour Validation             │  contour/contour_validator.py
              └─────────────────┬──────────────────┘
                                ▼
              ┌────────────────────────────────────┐
              │ 11. Contour Resampling             │  contour/contour_resampler.py
              └─────────────────┬──────────────────┘
                                ▼
              ┌────────────────────────────────────┐
              │ 12. Freeman Chain Coding           │  chain_code/freeman_chain.py
              └─────────────────┬──────────────────┘
                                ▼
              ┌────────────────────────────────────┐
              │ 13. Chain Normalization            │  chain_code/chain_normalizer.py
              └─────────────────┬──────────────────┘
                                ▼
              ┌────────────────────────────────────┐
              │ 14. Differential Chain Coding      │  chain_code/differential_chain.py,
              │                                    │  chain_code/chain_histogram.py
              └─────────────────┬──────────────────┘
                                ▼
              ┌────────────────────────────────────┐
              │ 15. Rack-relative Orientation      │  features/boundary_orientation.py
              └─────────────────┬──────────────────┘
                                ▼
              ┌────────────────────────────────────┐
              │ 16. Boundary Features              │  features/geometric_features.py
              └─────────────────┬──────────────────┘
                                ▼
              ┌────────────────────────────────────┐
              │ 17. Hand-Boundary Features         │  features/hand_boundary_features.py,
              │                                    │  features/contact_detector.py
              └─────────────────┬──────────────────┘
                                ▼
              ┌────────────────────────────────────┐
              │ 18. Temporal Boundary Tracking     │  temporal/boundary_tracker.py
              └─────────────────┬──────────────────┘
                                ▼
              ┌────────────────────────────────────┐
              │ 19. Boundary Change Analysis       │  temporal/boundary_change.py
              └─────────────────┬──────────────────┘
                                ▼
              ┌────────────────────────────────────┐
              │ 20. Optimization Cross-check       │  fusion/optimization_crosscheck.py
              └─────────────────┬──────────────────┘
                                ▼
              ┌────────────────────────────────────┐
              │ 21. Multi-frame Confirmation       │  temporal/confirmation.py
              └─────────────────┬──────────────────┘
                                ▼
              ┌────────────────────────────────────┐
              │ 22. Boundary Quality Gate          │  quality/boundary_quality_gate.py
              └─────────────────┬──────────────────┘
                                ▼
              ┌────────────────────────────────────┐
              │ 23. BoundaryOutputPacket Builder   │  output/boundary_packet_builder.py
              └─────────────────┬──────────────────┘
                                ▼
                       BoundaryOutputPacket
                                │
                                ▼
                 NEXT: 05 Perception Fusion
```

## Interfaces

| Direction | Interface | Contract |
|-----------|-----------|----------|
| Previous | Module 03 | `OptimizationOutputPacket` (interactions, hands, `RackReference`, `ObjectFrame`) |
| Previous | Module 01 | `FramePacket` lookup by `frame_id` |
| Next | Module 05 | `BoundaryOutputPacket` |

## Stages

### 1. Synchronization
- **Purpose:** Pair Module 03 output with its source frame.
- **Input:** `OptimizationOutputPacket`; frame-buffer lookup.
- **Processing:** Match by `frame_id`.
- **Output:** (`OptimizationOutputPacket`, `FramePacket`) pair.
- **Failure condition:** Frame evicted / mismatch → `INVALID_INPUT`.
- **Next component:** Input Validation.

### 2. Input Validation
- **Purpose:** Reject unusable input early.
- **Input:** Synchronized pair.
- **Processing:** Check statuses, `quality_ok` (per config), required fields.
- **Output:** Validated pair.
- **Failure condition:** Validation fails → packet with reason, no further processing.
- **Next component:** Target Selection.

### 3. Target Selection
- **Purpose:** Choose which object's boundary to analyse.
- **Input:** `InteractionCandidate`s, `ObjectFrame`.
- **Processing:** Pick the object the operator is interacting with (documented rule).
- **Output:** Target `track_id` + bbox.
- **Failure condition:** No target → `UNKNOWN` state, `NO_DETECTION`.
- **Next component:** Boundary ROI.

### 4. Boundary ROI
- **Purpose:** Restrict processing to the target region.
- **Input:** Target bbox, hand landmarks.
- **Processing:** Pad per config; clip to frame; keep offset.
- **Output:** ROI crop (copy) + offset.
- **Failure condition:** Zero-size ROI → reason recorded.
- **Next component:** ROI Preprocessing.

### 5. ROI Preprocessing
- **Purpose:** Prepare ROI for segmentation.
- **Input:** ROI crop.
- **Processing:** Optional blur, colour conversion, illumination normalization.
- **Output:** Preprocessed ROI.
- **Failure condition:** Invalid image → `ERROR`.
- **Next component:** Segmentation.

### 6. Segmentation
- **Purpose:** Separate object from background.
- **Input:** Preprocessed ROI.
- **Processing:** Configured method (e.g. HSV ranges per class).
- **Output:** Binary mask.
- **Failure condition:** Empty mask → reason recorded.
- **Next component:** Mask Cleanup.

### 7. Mask Cleanup
- **Purpose:** Remove noise and fill holes.
- **Input:** Binary mask.
- **Processing:** Morphological open/close; small-component removal.
- **Output:** Cleaned mask.
- **Failure condition:** Mask vanishes → reason recorded.
- **Next component:** Contour Extraction.

### 8. Contour Extraction
- **Purpose:** Get object outlines.
- **Input:** Cleaned mask.
- **Processing:** Extract external contours; add ROI offset (→ original-frame pixels).
- **Output:** Candidate contours.
- **Failure condition:** None found → reason recorded.
- **Next component:** Contour Association.

### 9. Contour Association
- **Purpose:** Pick the target's contour.
- **Input:** Candidates, target bbox, previous boundary.
- **Processing:** Overlap + temporal continuity rule.
- **Output:** One target contour.
- **Failure condition:** Ambiguous → reason recorded, no contour.
- **Next component:** Contour Validation.

### 10. Contour Validation
- **Purpose:** Reject implausible contours.
- **Input:** Target contour.
- **Processing:** Area/perimeter limits, closure.
- **Output:** Validated contour.
- **Failure condition:** Out of limits → rejected.
- **Next component:** Contour Resampling.

### 11. Contour Resampling
- **Purpose:** Make chain codes comparable across frames.
- **Input:** Validated contour.
- **Processing:** Uniform arc-length resampling.
- **Output:** Resampled contour (`contour_px`).
- **Failure condition:** Too few points → rejected.
- **Next component:** Freeman Chain Coding.

### 12. Freeman Chain Coding
- **Purpose:** Encode the boundary as directions.
- **Input:** Resampled contour.
- **Processing:** 8-direction Freeman code.
- **Output:** Raw chain code.
- **Failure condition:** Non-adjacent steps → resampling issue reported.
- **Next component:** Chain Normalization.

### 13. Chain Normalization
- **Purpose:** Remove start-point dependence.
- **Input:** Raw chain code.
- **Processing:** Start-point normalization.
- **Output:** `chain_code`.
- **Failure condition:** Empty chain → rejected.
- **Next component:** Differential Chain Coding.

### 14. Differential Chain Coding + Histogram
- **Purpose:** Rotation-tolerant shape description.
- **Input:** `chain_code`.
- **Processing:** Modulo-8 first difference; normalized direction histogram.
- **Output:** `differential_chain_code`, `chain_histogram`.
- **Failure condition:** Empty chain → skipped.
- **Next component:** Rack-relative Orientation.

### 15. Rack-relative Orientation
- **Purpose:** Orientation that is meaningful in microgravity.
- **Input:** Contour, `RackReference` from Module 03.
- **Processing:** Contour orientation relative to rack axes.
- **Output:** `orientation_deg_rack`.
- **Failure condition:** Reference invalid → `None` (no camera-up fallback).
- **Next component:** Boundary Features.

### 16. Boundary Features
- **Purpose:** Geometric description.
- **Input:** Contour.
- **Processing:** Area, perimeter, centroid (pixels).
- **Output:** `area_px`, `perimeter_px`, `centroid_px`.
- **Failure condition:** Degenerate contour → values `None`.
- **Next component:** Hand-Boundary Features.

### 17. Hand-Boundary Features
- **Purpose:** Hand-object contact evidence.
- **Input:** Hand landmarks, contour.
- **Processing:** Landmark-to-contour distances; contact rule from config.
- **Output:** `hand_contact`, `contact_confidence`.
- **Failure condition:** No hands → no contact evidence (not negative evidence).
- **Next component:** Temporal Boundary Tracking.

### 18. Temporal Boundary Tracking
- **Purpose:** History of the target boundary.
- **Input:** Per-frame features.
- **Processing:** Bounded history per target; reset on target change.
- **Output:** Boundary history.
- **Failure condition:** `frame_id` gap → history marked discontinuous.
- **Next component:** Boundary Change Analysis.

### 19. Boundary Change Analysis
- **Purpose:** Candidate boundary state.
- **Input:** Boundary history.
- **Processing:** Compare centroid, orientation, chain statistics, contact history.
- **Output:** Candidate `BoundaryState`.
- **Failure condition:** Insufficient history → `UNKNOWN`.
- **Next component:** Optimization Cross-check.

### 20. Optimization Cross-check
- **Purpose:** Compare with Module 03 evidence.
- **Input:** Candidate state, Module 03 motion/interaction.
- **Processing:** Agreement rules (report only).
- **Output:** `crosscheck_agrees`, disagreement reasons.
- **Failure condition:** Module 03 data unavailable → `None`.
- **Next component:** Multi-frame Confirmation.

### 21. Multi-frame Confirmation
- **Purpose:** Suppress flicker.
- **Input:** Candidate states over time.
- **Processing:** N-of-M confirmation.
- **Output:** `state_confirmed`, `confirmed_frames`.
- **Failure condition:** Not enough support → unconfirmed.
- **Next component:** Boundary Quality Gate.

### 22. Boundary Quality Gate
- **Purpose:** Report reliability.
- **Input:** All intermediate results.
- **Processing:** Check segmentation, contour, reference, confirmation.
- **Output:** `quality_ok`, `quality_reasons`, `confidence`.
- **Failure condition:** Any check fails → `quality_ok = False` with reasons.
- **Next component:** BoundaryOutputPacket Builder.

### 23. BoundaryOutputPacket Builder
- **Purpose:** Publish the module contract.
- **Input:** All results.
- **Processing:** Assemble shared schema; copy `frame_id`, `timestamp_s`, `target_track_id`.
- **Output:** `BoundaryOutputPacket`.
- **Failure condition:** Contract violation → `ERROR`.
- **Next component:** Module 05 — Perception Fusion.
