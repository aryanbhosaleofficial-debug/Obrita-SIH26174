# Module 04 — Boundary Detection Pipeline

> Receiving contract implemented: `boundary.input.input_validator.validate_boundary_input` checks real
> `OptimizationOutputPacket + FramePacket` metadata, identity and coordinate consistency.
> Segmentation, contours and boundary evidence remain scaffolded. See
> [the authoritative integration contract](../perception/INTEGRATION.md).

## Purpose

Module 04 analyses the **boundary (outline)** of the object the operator is interacting with, using
classical image processing (segmentation, contours, Freeman / differential chain codes), and produces
boundary-based evidence of whether the object is:

```text
stationary · moving · rotating · in contact with the hand · separating from the hand
```

This evidence is independent of Module 03's landmark-based reasoning, so Module 05 can cross-check
the two.

## Position in Main Pipeline

```text
03 Optimization ──OptimizationOutputPacket──┐
                                            ▼
External frame source ──FramePacket──► [04 Boundary] ──BoundaryOutputPacket──► 05 Perception Fusion
```

## Responsibilities

- Synchronizing `OptimizationOutputPacket` with the source frame by `frame_id`.
- Selecting the target object (from Module 03 interaction candidates).
- Boundary ROI generation and ROI preprocessing (on a copy).
- Segmentation (e.g. HSV) and morphological mask cleanup.
- Contour extraction, association with the target, validation and resampling.
- Freeman chain coding, start-point normalization, differential chain coding, chain histograms.
- Rack-relative boundary orientation (using Module 03's `RackReference`).
- Geometric and hand-boundary features; contact evidence.
- Temporal boundary tracking and change analysis → `BoundaryState` candidates.
- Cross-checking against Module 03 motion/interaction (report only).
- Multi-frame confirmation and a boundary quality gate.

## Non-Responsibilities

- Deciding whether an experiment procedure step is correct (Procedure FSM).
- Final activity recognition (Module 05).
- Object detection / tracking / `track_id` assignment (Module 02).
- Pose / hand landmark inference or rack-reference generation (Module 03).
- Modifying Module 03 outputs — the cross-check only *reports* agreement.

## Inputs

| Input | Source | Notes |
|-------|--------|-------|
| `OptimizationOutputPacket` | Module 03 | Interaction candidates, hands, `RackReference`, pass-through `ObjectFrame` |
| `FramePacket` (via frame buffer) | Module 01 | Source image; read-only |
| `configs/boundary.yaml` | Repository | ROI, segmentation, morphology, contour, chain code, temporal |

## Outputs

| Output | Consumer | Notes |
|--------|----------|-------|
| `BoundaryOutputPacket` (`shared/schemas/boundary_packet.py`) | Module 05 | Primary output |
| Debug frames (optional) | `outputs/debug_frames/` | ROI, mask, contour overlays |
| `ModuleStatus` + timing | Module 01 health monitor | |

## Internal Components

| Folder | Files | Role |
|--------|-------|------|
| `input/` | `input_synchronizer.py`, `input_validator.py`, `target_selector.py` | Pairing, validation, target choice |
| `roi/` | `boundary_roi.py` | Padded ROI around target (+ hands) |
| `preprocessing/` | `roi_preprocess.py`, `illumination.py` | Blur / colour conversion / illumination normalization |
| `segmentation/` | `foreground_segmenter.py`, `hsv_segmenter.py`, `mask_cleanup.py` | Binary mask |
| `contour/` | `contour_extractor.py`, `contour_association.py`, `contour_validator.py`, `contour_resampler.py` | Target contour |
| `chain_code/` | `freeman_chain.py`, `chain_normalizer.py`, `differential_chain.py`, `chain_histogram.py` | Shape encoding |
| `features/` | `geometric_features.py`, `boundary_orientation.py`, `hand_boundary_features.py`, `contact_detector.py` | Features + contact evidence |
| `temporal/` | `boundary_tracker.py`, `boundary_change.py`, `confirmation.py` | State over time |
| `fusion/` | `optimization_crosscheck.py` | Agreement with Module 03 (report only) |
| `quality/` | `boundary_quality_gate.py` | `quality_ok` + reasons |
| `output/` | `boundary_packet_builder.py` | Build `BoundaryOutputPacket` |

> `fusion/` here is a **local cross-check** only. Multi-source evidence fusion belongs to Module 05.

## Technology Stack

> This stack is chosen for the **SIH prototype**: offline demonstration, modular development and rapid
> iteration. It does **not** demonstrate spacecraft qualification, radiation tolerance, flight
> certification, real microgravity validation or mission reliability.

Module 04 is a **classical computer-vision module**. It runs no neural network; YOLO inference belongs
to Module 02 only.

### Core Technologies

| Technology | Purpose | Required / Optional | Why Used |
|------------|---------|---------------------|----------|
| Python 3 | Module implementation | Required | Same language as the rest of the pipeline. |
| OpenCV (`opencv-python`) | ROI extraction, colour conversion, HSV thresholding, binary masks, morphological opening/closing, contour detection, contour area, perimeter, bounding rectangle, convex hull, moments, shape features | Required (primary library) | Provides every classical segmentation and contour operation this module needs, offline and on the CPU. |
| NumPy | Binary mask arrays, contour arrays, chain-code arrays, histograms, geometric calculations, temporal differences, boundary vectors | Required | OpenCV masks and contours are NumPy arrays; chain-code maths is simple array arithmetic. |
| Custom Freeman chain code (Python + NumPy) | Boundary representation: Freeman code, start-point normalization, differential code, direction histogram | Required | A small, deterministic, fully testable local algorithm over OpenCV contour points. No deep-learning dependency is needed for chain coding. |
| SciPy (`scipy`) | Signal smoothing, distance calculations, curve processing | Optional | Only if NumPy/OpenCV do not cover a needed operation simply. |
| pytest | Tests on synthetic shapes with known answers | Development | |

### Python Libraries

| Library | Used For | Module Component |
|---------|----------|------------------|
| `cv2` (opencv-python) | ROI crop helpers, `cvtColor` (BGR→HSV), optional blur | `roi/boundary_roi.py`, `preprocessing/roi_preprocess.py` |
| `cv2` | Illumination normalization option (e.g. CLAHE / histogram equalization) | `preprocessing/illumination.py` |
| `cv2` | `inRange` HSV thresholding | `segmentation/hsv_segmenter.py`, `segmentation/foreground_segmenter.py` |
| `cv2` | `morphologyEx` (open/close), connected components for small-blob removal | `segmentation/mask_cleanup.py` |
| `cv2` | `findContours` | `contour/contour_extractor.py` |
| `cv2` | `contourArea`, `arcLength`, `boundingRect` | `contour/contour_validator.py`, `features/geometric_features.py` |
| `cv2` | `moments`, `convexHull`, `minAreaRect` | `features/geometric_features.py`, `features/boundary_orientation.py` |
| `cv2` | `pointPolygonTest` (signed distance from hand landmark to contour) | `features/hand_boundary_features.py`, `features/contact_detector.py` |
| `numpy` | Arc-length resampling | `contour/contour_resampler.py` |
| `numpy` | Freeman code, normalization, modulo-8 differences, histograms | `chain_code/freeman_chain.py`, `chain_code/chain_normalizer.py`, `chain_code/differential_chain.py`, `chain_code/chain_histogram.py` |
| `numpy` | Rack-relative orientation (projection onto `RackReference` axes) | `features/boundary_orientation.py` |
| `numpy` | Temporal differences of centroid / orientation / chain statistics | `temporal/boundary_change.py`, `fusion/optimization_crosscheck.py` |
| `collections.deque` | Boundary history and N-of-M confirmation | `temporal/boundary_tracker.py`, `temporal/confirmation.py` |
| `yaml` (PyYAML) | `configs/boundary.yaml` | Loaded once at module start-up and passed to components |
| `scipy` *(optional)* | Smoothing / distance utilities | `contour/contour_resampler.py`, `features/hand_boundary_features.py` |
| `pytest` | Tests | `tests/` |

### Segmentation Strategy

Initial prototype options (selected through `segmentation.method` in `configs/boundary.yaml`):

1. **HSV / colour thresholding**: per-class HSV ranges tuned on the demo setup.
2. **Object-specific thresholding**: different ranges or methods per object class.
3. **A mask supplied by a detector**, if one becomes available later (for example a segmentation model in
   Module 02). Module 04 would consume the mask, but it still would not run detection itself.

HSV segmentation is a **hackathon prototype approach** for a controlled demo environment. It is **not**
claimed to generalize to spacecraft lighting, materials or backgrounds.

### Required Technologies

- Python 3, `opencv-python`, `numpy`, `PyYAML`
- Custom Freeman chain-code implementation (Python + NumPy)
- Standard library: `collections.deque`
- Development: `pytest`

### Optional Technologies

- SciPy: smoothing, distance and curve-processing utilities, only where justified.

### Future Optimization Technologies

- None planned for the baseline. If profiling on the demo hardware shows a hotspot (e.g. resampling or
  chain coding implemented in pure Python loops), the first step is to vectorize with NumPy. GPU or
  compiled extensions are not planned.

### Recommended Stack Summary

| Technology | Purpose | Status |
|---|---|---|
| Python | Main implementation | Required |
| OpenCV | Segmentation/contours/morphology | Required |
| NumPy | Geometry/chain-code processing | Required |
| Custom Freeman Chain Code | Boundary representation | Required |
| SciPy | Additional numerical processing | Optional |
| pytest | Tests | Development |

## Technology Decisions

### Why These Technologies Were Selected

- **OpenCV** provides every classical operation the boundary pipeline needs (thresholding, morphology,
  contours, shape measures, point-to-contour distance) in one offline library already used by the project.
- **Custom Freeman chain code** is a few dozen lines of NumPy logic. Writing it locally keeps it
  transparent and testable on synthetic shapes with exact expected outputs.
- **HSV thresholding** is the simplest segmentation to tune and debug in a controlled demo setup.

### Alternatives Considered

| Area | Alternative | Why Not Used Initially |
|------|-------------|------------------------|
| Segmentation | Instance-segmentation model (e.g. a YOLO segmentation variant) | Needs labelled masks and training, and model inference belongs in Module 02. It could later supply masks to Module 04 (option 3 above). |
| Segmentation | Background subtraction (e.g. MOG2) | Assumes a static background, and a stationary object is gradually absorbed into the background, which conflicts with reporting the "stationary" state. |
| Segmentation | GrabCut, edge-based (Canny) segmentation | Higher per-frame cost (GrabCut) or more sensitive to texture and clutter (edges); can be evaluated later as config options. |
| Shape representation | Fourier descriptors, Hu moments, shape context | Chain codes were chosen by the team's design. Hu moments (available in OpenCV) or Fourier descriptors could be added later as extra features. |
| Numerical utilities | SciPy as a mandatory dependency | Not needed while NumPy/OpenCV cover the operations; kept optional. |

No alternative is claimed to be worse; none has been benchmarked by the team.

## CPU / GPU Considerations

### CPU

Module 04 runs entirely on the CPU. Processing is restricted to the target ROI, so its cost depends on ROI
size and contour length rather than on the full frame. Chain-code and resampling code should be
vectorized with NumPy rather than written as per-pixel Python loops.

### GPU

Not used and not required. OpenCV's CUDA modules need a custom OpenCV build and are not part of this
prototype.

### Hardware Considerations

- Lighting and camera exposure strongly affect colour segmentation; tuned HSV ranges are valid only for
  the setup they were tuned on.
- Runtime performance must be benchmarked on the final demo hardware.

## Offline Compatibility

After the dependencies are installed and the configuration is prepared, Module 04 must **not** require
internet access, cloud inference, external APIs or ground-station connectivity.

- Module 04 uses **no model files**, only configuration and the source frames from Module 01.
- Debug frames are written locally to `outputs/debug_frames/`.
- Sample ROI images for offline tuning live in `data/samples/`.

## Shared Schemas Used

- Consumes: `OptimizationOutputPacket` (incl. `ObjectFrame`, `SpatialFeaturePacket`, `RackReference`), `FramePacket`
- Produces: `BoundaryOutputPacket`
- Enums: `BoundaryState`, `InteractionState`, `ModuleStatus`

## Configuration

`configs/boundary.yaml`: `input`, `roi`, `preprocessing`, `segmentation` (HSV ranges per class),
`morphology`, `contour`, `chain_code`, `features`, `temporal`, `crosscheck`, `quality`.

Segmentation ranges depend on the real objects, background and lighting, and must be tuned on the
demo setup. They are `null` / empty placeholders now.

## Dependencies

- Runtime: `opencv-python`, `numpy`, `PyYAML` + standard library (`collections.deque`).
- Optional: `scipy`.
- Development: `pytest`.
- No YOLO, PyTorch or other deep-learning dependency.
- `shared/` package. No network access. See [Technology Stack](#technology-stack).

## Developer Ownership

| Area | Owner |
|------|-------|
| Module 04 (all folders) | Teammate 5 — Boundary Detection *(name to be filled in by the team)* |

## How to Run Independently

Once implemented, from the repository root:

```bash
python scripts/run_boundary.py
```

Displays ROI, mask, contour, chain code and boundary state. A planned option allows tuning
segmentation on saved ROI images in `data/samples/` without running the full pipeline.

## Testing

```bash
python -m pytest 04_boundary/tests
```

| Test file | Covers |
|-----------|--------|
| `test_segmentation.py` | Config ranges, mask cleanup, empty masks, no source modification |
| `test_contours.py` | ROI offsets, target association, validation, resampling |
| `test_chain_code.py` | Freeman code on synthetic shapes, normalization, rotation invariance, histograms |
| `test_contact.py` | Contact / no-contact evidence |
| `test_boundary_tracking.py` | Stationary / moving / rotating synthetic objects, confirmation |
| `test_boundary_packet.py` | Metadata copy, shared schema, cross-check, quality reasons |

All tests are currently skipped placeholders. Chain-code tests should use synthetic shapes with
known answers so they can be verified exactly.

## Integration Contract

- `frame_id`, `timestamp_s`, `target_track_id` copied **unchanged** from `OptimizationOutputPacket`.
- `contour_px`, `centroid_px` are original source-frame pixels.
- `chain_code` values are in `0..7` (8-connectivity) with the numbering convention documented in `chain_code/freeman_chain.py`.
- `orientation_deg_rack` is relative to the rack reference x-axis, or `None` when the reference is invalid.
- `boundary_state` uses `BoundaryState`; it is evidence, not a procedure decision.
- `crosscheck_agrees` only reports agreement; Module 03 data is never modified.
- `quality_ok == False` always has at least one `quality_reasons` entry.

## Error / Failure Handling

| Failure | Behaviour |
|---------|-----------|
| No target object selected | Packet with `BoundaryState.UNKNOWN`, `NO_DETECTION` |
| Empty / noisy mask | Contour rejected; quality reason recorded |
| Multiple candidate contours | Association rule picks one or reports ambiguity |
| Rack reference invalid | `orientation_deg_rack = None`; rotation state not reported |
| Upstream `quality_ok == False` | Behaviour per `input.require_optimization_quality` |
| Frame evicted from buffer | `INVALID_INPUT` |

## Current Limitations

- Colour segmentation is sensitive to lighting and object colour; values are untuned placeholders.
- 2D image boundary only; out-of-plane rotation is not measured.
- Single target object per frame.

## Future Improvements

- Alternative segmentation methods selectable from config.
- Shape matching against stored reference chain codes per object class.
- Multiple simultaneous targets.
