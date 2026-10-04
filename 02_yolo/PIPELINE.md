# Module 02 — YOLO Pipeline

## Overview

```text
        PREVIOUS MODULE: 01 Perception Core
                          │
                          ▼
                     FramePacket
                          │
                          ▼
           ┌───────────────────────────────┐
           │ 1. Letterbox Preprocessing    │  preprocessing/letterbox.py
           └───────────────┬───────────────┘
                           │ letterboxed copy + LetterboxParams
                           ▼
           ┌───────────────────────────────┐
           │ 2. Normalization              │  preprocessing/normalize.py
           └───────────────┬───────────────┘
                           │
                           ▼
           ┌───────────────────────────────┐
           │ 3. YOLO Inference             │  inference/yolo_loader.py
           │                               │  inference/yolo_inference.py
           └───────────────┬───────────────┘
                           │ raw outputs
                           ▼
           ┌───────────────────────────────┐
           │ 4. Post-processing (NMS)      │  inference/postprocess.py
           └───────────────┬───────────────┘
                           │ candidates (letterboxed coords)
                           ▼
           ┌───────────────────────────────┐
           │ 5. Coordinate Restoration     │  preprocessing/coordinate_restore.py
           └───────────────┬───────────────┘
                           │ candidates (ORIGINAL-frame pixels)
                           ▼
           ┌───────────────────────────────┐
           │ 6. Detection Filtering        │  detection/detection_filter.py
           │    + BBox Validation          │  detection/bbox_validator.py
           └───────────────┬───────────────┘
                           │
                           ▼
           ┌───────────────────────────────┐
           │ 7. Tracking                   │  tracking/object_tracker.py
           │    + Track Lifecycle          │  tracking/track_manager.py, track_state.py
           └───────────────┬───────────────┘
                           │
                           ▼
           ┌───────────────────────────────┐
           │ 8. Object-State Generation    │  detection/object_state.py
           └───────────────┬───────────────┘
                           │
                           ▼
           ┌───────────────────────────────┐
           │ 9. Multi-frame Stability      │  stability/detection_stability.py
           └───────────────┬───────────────┘
                           │
                           ▼
           ┌───────────────────────────────┐
           │ 10. Reference-Anchor          │  reference/anchor_extractor.py
           │     Extraction                │
           └───────────────┬───────────────┘
                           │
                           ▼
           ┌───────────────────────────────┐
           │ 11. ObjectFrame Builder       │  output/object_frame_builder.py
           └───────────────┬───────────────┘
                           │
                           ▼
                      ObjectFrame
                           │
                           ▼
        NEXT MODULE: 03 Optimization Sequence
        (also passed read-only to 04 and 05 via OptimizationOutputPacket.object_frame)
```

> Note: the requested high-level order lists "Detection filtering" before "Coordinate restoration".
> Either order is valid as long as **no letterboxed coordinate leaves this module**. The diagram
> restores first so that box validation (stage 6) checks boxes against the original frame bounds.

## Interfaces

| Direction | Interface | Contract |
|-----------|-----------|----------|
| Previous | Module 01 | `FramePacket` (read-only image, `frame_id`, `timestamp_s`, actual size) |
| Next | Module 03 | `ObjectFrame` with original-frame coordinates |
| Pass-through | Modules 04, 05 | Same `ObjectFrame`, read-only, via `OptimizationOutputPacket.object_frame` |
| Health | Module 01 | `ModuleStatus` + measured timing |

## Stages

### 1. Letterbox Preprocessing

- **Purpose:** Fit the frame to the model input size without distortion.
- **Input:** `FramePacket.image`.
- **Processing:** Compute scale and padding; resize and pad a **copy**.
- **Output:** Letterboxed image, `LetterboxParams(scale, pad_x, pad_y)`.
- **Failure condition:** Empty / malformed image → `INVALID_INPUT`.
- **Next component:** Normalization.

### 2. Normalization

- **Purpose:** Convert to the model's expected format.
- **Input:** Letterboxed image.
- **Processing:** Channel order, dtype and scaling as required by the model.
- **Output:** Model-ready array/tensor.
- **Failure condition:** Unsupported format → `ERROR`.
- **Next component:** YOLO Inference.

### 3. YOLO Inference

- **Purpose:** Detect objects.
- **Input:** Model-ready tensor; model loaded from local path.
- **Processing:** Forward pass on the configured device.
- **Output:** Raw outputs.
- **Failure condition:** Model file missing (start-up error), runtime exception (`ERROR` for the frame).
- **Next component:** Post-processing.

### 4. Post-processing

- **Purpose:** Turn raw outputs into candidate detections.
- **Input:** Raw outputs.
- **Processing:** Decode boxes/scores/classes; NMS with configured IoU threshold.
- **Output:** Candidates in letterboxed coordinates.
- **Failure condition:** Malformed outputs → `ERROR`.
- **Next component:** Coordinate Restoration.

### 5. Coordinate Restoration

- **Purpose:** Express boxes in original source-frame pixels.
- **Input:** Candidates + `LetterboxParams`.
- **Processing:** Subtract padding, divide by scale, clip to original image bounds.
- **Output:** Candidates in original-frame pixels.
- **Failure condition:** Box degenerates after clipping → flagged for rejection.
- **Next component:** Detection Filtering + BBox Validation.

### 6. Detection Filtering + BBox Validation

- **Purpose:** Keep only usable detections.
- **Input:** Restored candidates.
- **Processing:** Confidence threshold, allowed classes, reject non-finite/zero-area/out-of-frame boxes.
- **Output:** Valid detections.
- **Failure condition:** None remain → continue with empty list (`NO_DETECTION` at the end).
- **Next component:** Tracking.

### 7. Tracking + Track Lifecycle

- **Purpose:** Persistent identity per physical object.
- **Input:** Valid detections for this frame; existing tracks.
- **Processing:** Associate detections to tracks; create / confirm / lose / reacquire / remove tracks; compute track quality.
- **Output:** Detections with `track_id`, `track_status`, `track_quality`, age counters.
- **Failure condition:** Association failure → new tentative tracks; logged.
- **Next component:** Object-State Generation.

### 8. Object-State Generation

- **Purpose:** Fill the shared `DetectedObject` entries.
- **Input:** Tracked detections.
- **Processing:** Map fields onto `DetectedObject`.
- **Output:** `list[DetectedObject]`.
- **Failure condition:** Missing fields → entry dropped and logged.
- **Next component:** Multi-frame Stability.

### 9. Multi-frame Stability

- **Purpose:** Suppress flicker.
- **Input:** `DetectedObject` list + per-track history.
- **Processing:** Configured N-of-M rule per track.
- **Output:** `is_stable` flag set.
- **Failure condition:** Insufficient history → `is_stable = False`.
- **Next component:** Reference-Anchor Extraction.

### 10. Reference-Anchor Extraction

- **Purpose:** Provide the rack/payload anchor used for rack-relative reasoning downstream.
- **Input:** Stable detections whose class has a reference role.
- **Processing:** Select the most stable anchor per role.
- **Output:** `list[ReferenceAnchor]` (possibly empty).
- **Failure condition:** No anchor visible → empty list (never fabricated).
- **Next component:** ObjectFrame Builder.

### 11. ObjectFrame Builder

- **Purpose:** Publish the shared contract.
- **Input:** Detections, anchors, `FramePacket` metadata.
- **Processing:** Copy `frame_id` / `timestamp_s` / size unchanged; set `ModuleStatus`.
- **Output:** `ObjectFrame`.
- **Failure condition:** Contract violation → `ERROR`, logged.
- **Next component:** Module 03 — Optimization Sequence.
