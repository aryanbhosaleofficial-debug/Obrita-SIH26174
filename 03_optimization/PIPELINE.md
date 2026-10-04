> Historical team plan; partially implemented. Current ownership, active entry points
> and implementation limits are defined in this module README and
> [perception/INTEGRATION.md](../perception/INTEGRATION.md). Module 01 publishes
> PreparedFrame; continuity/confirmation and rack calibration belong to Module 03.
> The anchor-derived reference plan below is historical. The current
> ObjectFrame.reference_anchors field is reserved and always empty; active Module 03
> uses its manual/ArUco transformer and publishes SpatialFeaturePacket.reference_frame.

# Module 03 — Optimization Sequence Pipeline

## Overview

```text
   PREVIOUS MODULES: 02 YOLO (ObjectFrame) + 01 Perception Core (FramePacket via frame buffer)
                                   │
   ════════════════ SPATIAL SECTION — Teammate 3 ══════════════════
                                   ▼
                  ┌────────────────────────────────┐
                  │ S1. Input Synchronization      │  input/input_synchronizer.py
                  │     + Validation               │  input/input_validator.py
                  └───────────────┬────────────────┘
                                  ▼
                  ┌────────────────────────────────┐
                  │ S2. ROI Generation             │  roi/human_roi.py, roi/hand_roi.py
                  └───────────────┬────────────────┘
                                  ▼
                  ┌────────────────────────────────┐
                  │ S3. Pose Inference             │  pose/pose_detector.py, pose_validator.py
                  └───────────────┬────────────────┘
                                  ▼
                  ┌────────────────────────────────┐
                  │ S4. Hand Inference             │  hands/hand_detector.py, hand_validator.py,
                  │                                │  hands/handedness.py
                  └───────────────┬────────────────┘
                                  ▼
                  ┌────────────────────────────────┐
                  │ S5. Landmark Validation        │  landmarks/landmark_filter.py
                  └───────────────┬────────────────┘
                                  ▼
                  ┌────────────────────────────────┐
                  │ S6. Skeleton Generation        │  skeleton/*
                  └───────────────┬────────────────┘
                                  ▼
                  ┌────────────────────────────────┐
                  │ S7. Temporal Landmark          │  landmarks/landmark_smoother.py,
                  │     Filtering                  │  landmarks/missing_landmarks.py
                  └───────────────┬────────────────┘
                                  ▼
                  ┌────────────────────────────────┐
                  │ S8. Relative-Depth             │  landmarks/relative_depth.py
                  │     Representation (pseudo-3D) │
                  └───────────────┬────────────────┘
                                  ▼
                  ┌────────────────────────────────┐
                  │ S9. Rack-Reference Generation  │  reference_frame/rack_reference.py,
                  │                                │  reference_frame/reference_validator.py
                  └───────────────┬────────────────┘
                                  ▼
                  ┌────────────────────────────────┐
                  │ S10. Rack-Relative             │  reference_frame/coordinate_transform.py,
                  │      Transformation            │  reference_frame/orientation.py
                  └───────────────┬────────────────┘
                                  ▼
                  ┌────────────────────────────────┐
                  │ S11. SpatialFeaturePacket      │  spatial_output/spatial_packet_builder.py
                  │      Builder                   │
                  └───────────────┬────────────────┘
                                  │
                        SpatialFeaturePacket   ◄── HAND-OVER (shared contract)
                                  │
   ════════════════ TEMPORAL SECTION — Teammate 4 ═════════════════
                                  ▼
                  ┌────────────────────────────────┐
                  │ T1. Motion Features            │  motion/*
                  └───────────────┬────────────────┘
                                  ▼
                  ┌────────────────────────────────┐
                  │ T2. Hand-Object Features       │  interaction/hand_object_distance.py,
                  │                                │  object_association.py, proximity.py
                  └───────────────┬────────────────┘
                                  ▼
                  ┌────────────────────────────────┐
                  │ T3. Temporal Sequence          │  temporal/sequence_buffer.py,
                  │                                │  temporal/temporal_filter.py
                  └───────────────┬────────────────┘
                                  ▼
                  ┌────────────────────────────────┐
                  │ T4. Gesture Recognition        │  gesture/*
                  └───────────────┬────────────────┘
                                  ▼
                  ┌────────────────────────────────┐
                  │ T5. Interaction Recognition    │  interaction/interaction_generator.py
                  └───────────────┬────────────────┘
                                  ▼
                  ┌────────────────────────────────┐
                  │ T6. Multi-frame Confirmation   │  temporal/multi_frame_confirmation.py
                  └───────────────┬────────────────┘
                                  ▼
                  ┌────────────────────────────────┐
                  │ T7. Quality Gate               │  quality/perception_quality_gate.py
                  └───────────────┬────────────────┘
                                  ▼
                  ┌────────────────────────────────┐
                  │ T8. OptimizationOutputPacket   │  output/optimization_packet_builder.py
                  │     Builder                    │
                  └───────────────┬────────────────┘
                                  ▼
                       OptimizationOutputPacket
                                  │
                ┌─────────────────┴─────────────────┐
                ▼                                   ▼
   NEXT: 04 Boundary Detection          NEXT: 05 Perception Fusion
```

## Interfaces

| Direction | Interface | Contract |
|-----------|-----------|----------|
| Previous | Module 02 | `ObjectFrame` (original-frame boxes, `track_id`, `ReferenceAnchor`s) |
| Previous | Module 01 | `FramePacket` lookup by `frame_id` |
| Internal | Teammate 3 → Teammate 4 | `SpatialFeaturePacket` |
| Next | Module 04 | `OptimizationOutputPacket` (+ pass-through `object_frame`, `spatial`) |
| Next | Module 05 | `OptimizationOutputPacket` |

## Spatial Stages (Teammate 3)

### S1. Input Synchronization + Validation
- **Purpose:** Pair `ObjectFrame` with its source frame.
- **Input:** `ObjectFrame`, frame-buffer lookup.
- **Processing:** Match by `frame_id`; check statuses; check an operator track exists.
- **Output:** Validated (`FramePacket`, `ObjectFrame`) pair.
- **Failure condition:** Frame evicted / mismatched → `INVALID_INPUT`; no operator → `NO_DETECTION`.
- **Next component:** ROI Generation.

### S2. ROI Generation
- **Purpose:** Focus inference on the operator and hands.
- **Input:** Operator box, previous hand/wrist positions.
- **Processing:** Select operator track; pad ROIs per config; keep ROI offsets.
- **Output:** Operator ROI, hand ROIs (with offsets).
- **Failure condition:** ROI outside frame / zero size → skip, record reason.
- **Next component:** Pose Inference.

### S3. Pose Inference
- **Purpose:** Body landmarks.
- **Input:** Operator ROI.
- **Processing:** Local pose model; map to original-frame pixels; validate visibility/presence.
- **Output:** Body landmarks (`x_px`, `y_px`, `z_rel`, scores).
- **Failure condition:** No pose found → empty landmarks, `DEGRADED`.
- **Next component:** Hand Inference.

### S4. Hand Inference
- **Purpose:** Hand landmarks and handedness.
- **Input:** Hand ROIs.
- **Processing:** Local hand model; map to original pixels; resolve handedness (mirroring aware).
- **Output:** `HandLandmarks` list.
- **Failure condition:** No hands → empty list (valid result).
- **Next component:** Landmark Validation.

### S5. Landmark Validation
- **Purpose:** Remove unreliable landmarks.
- **Input:** Pose + hand landmarks.
- **Processing:** Confidence thresholds, outlier jumps, plausibility checks.
- **Output:** Landmarks with `is_valid` flags.
- **Failure condition:** Too few valid landmarks → recorded for quality gate.
- **Next component:** Skeleton Generation.

### S6. Skeleton Generation
- **Purpose:** Structured body/hand skeleton.
- **Input:** Valid landmarks, connection tables.
- **Processing:** Build bones whose endpoints are valid.
- **Output:** `skeleton_bones`.
- **Failure condition:** Missing endpoints → bone omitted.
- **Next component:** Temporal Landmark Filtering.

### S7. Temporal Landmark Filtering
- **Purpose:** Stable landmarks over time.
- **Input:** Landmarks history.
- **Processing:** Smoothing; bounded interpolation of short gaps (flagged `is_interpolated`).
- **Output:** Smoothed landmarks.
- **Failure condition:** Gap longer than configured limit → landmark stays invalid.
- **Next component:** Relative-Depth Representation.

### S8. Relative-Depth Representation
- **Purpose:** Consistent pseudo-3D (relative XYZ).
- **Input:** Smoothed landmarks with model `z`.
- **Processing:** Normalize `z` relative to a body reference; **no metric conversion**.
- **Output:** Landmarks with normalized `z_rel`.
- **Failure condition:** Reference landmark missing → `z_rel = None`.
- **Next component:** Rack-Reference Generation.

### S9. Rack-Reference Generation
- **Purpose:** Define a reference frame tied to the rack/payload.
- **Input:** `ReferenceAnchor`s from `ObjectFrame`.
- **Processing:** Origin + axes from anchor; temporal consistency check.
- **Output:** `RackReference` with `is_valid`.
- **Failure condition:** No / unstable anchor → `is_valid = False` (no camera-up fallback).
- **Next component:** Rack-Relative Transformation.

### S10. Rack-Relative Transformation
- **Purpose:** Express landmarks and orientation relative to the rack.
- **Input:** Landmarks + valid `RackReference`.
- **Processing:** Coordinate transform; orientation relative to rack axes.
- **Output:** `rack_relative_pose` and orientations.
- **Failure condition:** Invalid reference → transformation skipped, quality reason recorded.
- **Next component:** SpatialFeaturePacket Builder.

### S11. SpatialFeaturePacket Builder
- **Purpose:** Hand-over to Teammate 4.
- **Input:** All spatial results.
- **Processing:** Assemble shared schema; copy `frame_id`/`timestamp_s`.
- **Output:** `SpatialFeaturePacket`.
- **Failure condition:** Contract violation → `ERROR`.
- **Next component:** T1 Motion Features.

## Temporal Stages (Teammate 4)

### T1. Motion Features
- **Purpose:** Describe how the operator moves.
- **Input:** `SpatialFeaturePacket` sequence.
- **Processing:** Joint angles; displacement, velocity, acceleration from `timestamp_s` differences; rack-relative direction.
- **Output:** `MotionFeatures`.
- **Failure condition:** `frame_id` gap / invalid landmarks → value omitted, not extrapolated.
- **Next component:** Hand-Object Features.

### T2. Hand-Object Features
- **Purpose:** Relate hands to objects.
- **Input:** Hand landmarks, object boxes from `ObjectFrame`.
- **Processing:** Distances (normalized units), association to at most one object per hand, proximity levels.
- **Output:** Per-hand association + distance + proximity.
- **Failure condition:** No hands or no objects → empty result.
- **Next component:** Temporal Sequence.

### T3. Temporal Sequence
- **Purpose:** Windowed history for temporal reasoning.
- **Input:** Per-frame features.
- **Processing:** Sliding window ordered by `frame_id`; hysteresis filtering.
- **Output:** Feature window with gap information.
- **Failure condition:** Window incomplete → recorded for quality gate.
- **Next component:** Gesture Recognition.

### T4. Gesture Recognition
- **Purpose:** Recognize configured gestures.
- **Input:** Gesture features over the window.
- **Processing:** Rule-based or local model (decision pending).
- **Output:** `GestureResult` (`unknown` when unsure).
- **Failure condition:** Insufficient evidence → `unknown`.
- **Next component:** Interaction Recognition.

### T5. Interaction Recognition
- **Purpose:** Hand-object interaction state.
- **Input:** Proximity, motion, association history.
- **Processing:** Map to `InteractionState`.
- **Output:** `InteractionCandidate` list.
- **Failure condition:** Ambiguous evidence → `UNKNOWN` state.
- **Next component:** Multi-frame Confirmation.

### T6. Multi-frame Confirmation
- **Purpose:** Suppress flicker.
- **Input:** Gesture + interaction results over the window.
- **Processing:** N-of-M confirmation.
- **Output:** `confirmed` flags.
- **Failure condition:** Not enough supporting frames → `confirmed = False`.
- **Next component:** Quality Gate.

### T7. Quality Gate
- **Purpose:** Tell downstream modules how reliable this packet is.
- **Input:** All Module 03 results.
- **Processing:** Visibility, reference validity, window completeness checks.
- **Output:** `quality_ok`, `quality_reasons`.
- **Failure condition:** Any check fails → `quality_ok = False` with reasons.
- **Next component:** OptimizationOutputPacket Builder.

### T8. OptimizationOutputPacket Builder
- **Purpose:** Publish the module contract.
- **Input:** All results + pass-through `object_frame`, `spatial`.
- **Processing:** Assemble shared schema; copy `frame_id`, `timestamp_s`, `target_track_id`.
- **Output:** `OptimizationOutputPacket`.
- **Failure condition:** Contract violation → `ERROR`.
- **Next component:** Module 04 — Boundary Detection and Module 05 — Perception Fusion.
