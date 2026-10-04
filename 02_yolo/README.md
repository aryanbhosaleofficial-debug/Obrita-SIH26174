# Module 02 — YOLO Pipeline

> Implementation status: **scaffold only**. Interfaces and responsibilities are defined; algorithms are not implemented.

## Purpose

Module 02 detects and tracks the operator, experiment objects and rack/payload reference objects
in each frame, and publishes them as an `ObjectFrame` whose coordinates are in the **original
source frame**.

```text
FramePacket
   ↓
Preprocessing (letterbox, normalize)
   ↓
YOLO inference
   ↓
Post-processing + detection filtering
   ↓
Coordinate restoration (→ original source frame)
   ↓
Tracking
   ↓
Object-state generation
   ↓
Multi-frame stability
   ↓
Reference-anchor extraction
   ↓
ObjectFrame
```

## Position in Main Pipeline

```text
01 Perception Core ──FramePacket──► [02 YOLO] ──ObjectFrame──► 03 Optimization Sequence
                                                     │
                                                     └─ passed through (read-only) inside
                                                        OptimizationOutputPacket.object_frame
                                                        to 04 Boundary and 05 Fusion
```

## Responsibilities

- Object detection with a locally stored YOLO model.
- Confidence and class filtering (thresholds from config).
- Restoring box coordinates from letterboxed model space to original source-frame pixels.
- Multi-object tracking with persistent `track_id`.
- Track quality and lifecycle (`tentative`, `confirmed`, `lost`, `reacquired`).
- Multi-frame detection confirmation (`is_stable`).
- Rack / payload reference-anchor detection (`ReferenceAnchor`).

## Non-Responsibilities

- Camera capture, `frame_id` / timestamp assignment (Module 01).
- Pose, hands, skeleton, rack-relative coordinate transforms (Module 03).
- Hand-object interaction or gesture decisions (Module 03).
- Segmentation, contours, chain codes (Module 04).
- Activity recognition (Module 05) or procedure validation (Procedure FSM).
- Model training (out of scope for this runtime module).

## Inputs

| Input | Source | Notes |
|-------|--------|-------|
| `FramePacket` | Module 01 | `image` is the original source frame — read only |
| `configs/yolo.yaml` | Repository | Model path, thresholds, tracking, stability |
| `configs/classes.yaml` | Repository | Class names, ids, roles (operator / reference / experiment_object) |
| Model weights | `02_yolo/models/` | Local file only; never downloaded at runtime |

## Outputs

| Output | Consumer | Notes |
|--------|----------|-------|
| `ObjectFrame` (`shared/schemas/object_frame.py`) | Module 03 (and 04/05 via pass-through) | Primary output |
| `ModuleStatus` + timing | Module 01 health monitor | |

## Internal Components

| Folder | File | Role |
|--------|------|------|
| `models/` | `README.md` | Where local weights go + model record |
| `preprocessing/` | `letterbox.py` | Resize + pad a copy; return `LetterboxParams` |
| | `normalize.py` | Channel order / dtype for the model |
| | `coordinate_restore.py` | Letterboxed → original-frame coordinates |
| `inference/` | `yolo_loader.py` | Load local weights, device selection |
| | `yolo_inference.py` | Run model |
| | `postprocess.py` | Decode outputs, NMS |
| `detection/` | `detection_filter.py` | Confidence / class filtering |
| | `bbox_validator.py` | Reject invalid boxes |
| | `object_state.py` | Fill `DetectedObject` fields |
| `tracking/` | `object_tracker.py` | Associate detections over time |
| | `track_manager.py` | Track lifecycle + quality |
| | `track_state.py` | Track state transitions |
| `stability/` | `detection_stability.py` | N-of-M confirmation |
| `reference/` | `anchor_extractor.py` | Rack/payload `ReferenceAnchor`s |
| `output/` | `object_frame_builder.py` | Build `ObjectFrame` |

## Technology Stack

> This stack is chosen for the **SIH prototype**: offline demonstration, modular development and rapid
> iteration. It does **not** demonstrate spacecraft qualification, radiation tolerance, flight
> certification, real microgravity validation or mission reliability.

### Core Technologies

| Technology | Purpose | Required / Optional | Why Used |
|------------|---------|---------------------|----------|
| Python 3 | Module implementation | Required | Same language as every other module; `ObjectFrame` is passed in-process. |
| Ultralytics YOLO (`ultralytics`) | Model loading, object detection inference, built-in preprocessing/post-processing where appropriate, tracking integration if selected | Required | Lightweight YOLO-family models suit real-time/offline prototypes. Pretrained or custom-trained weights run locally on CPU or GPU, and the Python API returns boxes, classes, confidences (and track ids when tracking is on) with little glue code. Whether a given model is fast enough on our hardware must be **measured**, not assumed. |
| PyTorch (`torch`) | Runtime underneath Ultralytics: model execution, tensor operations, GPU acceleration; training/fine-tuning (development time) | Required by the current YOLO approach | Ultralytics' native backend. We do **not** write our own inference loop on top of PyTorch where Ultralytics already handles it. |
| OpenCV (`opencv-python`) | Frame manipulation, resize/letterbox (custom path), image conversion, bbox debug visualization | Required | Standard, offline image operations on the NumPy frames from Module 01. Debug drawing on a **copy** of the frame. |
| NumPy | Bbox arrays, centroids, IoU/geometry, coordinate restoration and clipping, tracking helpers, detection history buffers | Required | Vectorized box maths without extra dependencies. |
| Tracker: ByteTrack / BoT-SORT (via Ultralytics) | Persistent `track_id` across frames | Configurable (candidate) | Available through Ultralytics without extra packages; final choice is made in `configs/yolo.yaml` → `tracking.method` after testing. |
| pytest | Detection, coordinate-restoration, tracking and `ObjectFrame` tests | Development | |

### Python Libraries

| Library | Used For | Module Component |
|---------|----------|------------------|
| `ultralytics` | `YOLO(<local path>)`, `predict()` / `track()` | `inference/yolo_loader.py`, `inference/yolo_inference.py`, `tracking/object_tracker.py` |
| `torch` | Device selection (e.g. `torch.cuda.is_available()`); runtime under Ultralytics | `inference/yolo_loader.py` |
| `cv2` (opencv-python) | Resize / letterbox and colour conversion on the custom path; debug overlays | `preprocessing/letterbox.py`, `preprocessing/normalize.py`, `scripts/run_yolo.py` |
| `numpy` | Box arrays, clipping, IoU, centroids, restore maths | `preprocessing/coordinate_restore.py`, `detection/*`, `reference/anchor_extractor.py` |
| `collections.deque` | Per-track detection history for N-of-M stability | `stability/detection_stability.py` |
| `dataclasses`, `enum` | `LetterboxParams`, track state values | `preprocessing/letterbox.py`, `tracking/track_state.py` |
| `yaml` (PyYAML) | `yolo.yaml`, `classes.yaml` | `inference/yolo_loader.py`, `detection/detection_filter.py` |
| `pytest` | Tests | `tests/` |

**Avoiding duplicated work:** when inference goes through Ultralytics `predict()`/`track()`, Ultralytics
performs letterboxing itself and returns boxes already scaled to the original image. In that case
`preprocessing/letterbox.py` and `preprocessing/coordinate_restore.py` must not repeat the work; they
verify the "original source-frame coordinates" contract (and the tests in `test_coordinate_restore.py`
still apply). They do the actual work only on a custom inference path (e.g. a future exported model).

### Object Tracking

- **Preferred initial approach:** an Ultralytics-supported tracker, selected via `tracking.method`.
- **Candidates (configurable, not final):** ByteTrack, BoT-SORT.
- Whatever backend is chosen, Module 02 must provide per object:
  persistent `track_id`, track state (`tentative` / `confirmed` / `lost` / `reacquired`), track quality,
  and lost/reacquired information.
- If the tracker backend does not expose lifecycle or quality directly, `tracking/track_manager.py` and
  `tracking/track_state.py` compute them from the backend's per-frame track ids.
- Appearance-based re-identification options stay disabled unless their weights are stored locally.

### Required Technologies

- Python 3, `ultralytics`, `torch`, `opencv-python`, `numpy`, `PyYAML`
- One Ultralytics-supported tracker (ByteTrack or BoT-SORT), chosen in config
- Development: `pytest`

### Optional Technologies

- The tracker candidate not selected as default (kept switchable through config for comparison).
- Fine-tuning YOLO on team-collected, labelled data with Ultralytics + PyTorch. This is a
  development-time activity on a local machine and is not part of the runtime pipeline.

### Future Optimization Technologies

Only after the baseline pipeline works end-to-end:

```text
PyTorch / Ultralytics first
        ↓
validate the full pipeline
        ↓
export the model (Ultralytics export)
        ↓
optional ONNX Runtime / TensorRT / OpenVINO optimization
        ↓
re-validate outputs and re-measure on the demo hardware
```

| Technology | Target | Note |
|------------|--------|------|
| ONNX Runtime | CPU / various accelerators | Portable exported-model runtime |
| TensorRT | NVIDIA GPUs | NVIDIA-specific acceleration |
| OpenVINO | Intel CPUs / GPUs | Intel-specific acceleration |

None of these is required for the first functional prototype, and none is listed in `requirements.txt`.

### Recommended Stack Summary

| Technology | Purpose | Status |
|---|---|---|
| Python | Implementation | Required |
| Ultralytics YOLO | Detection | Required |
| PyTorch | Model runtime/training | Required by current YOLO approach |
| OpenCV | Frame processing/debug visualization | Required |
| NumPy | Detection geometry | Required |
| ByteTrack/BoT-SORT | Tracking option | Configurable |
| ONNX Runtime | Edge optimization | Future/Optional |
| TensorRT | NVIDIA acceleration | Future/Optional |
| OpenVINO | Intel acceleration | Future/Optional |
| pytest | Testing | Development |

## Technology Decisions

### Why These Technologies Were Selected

- **Ultralytics YOLO** gives detection, tracking integration and later model export in one locally
  installed package, which keeps Module 02 small enough for a hackathon team to build and test.
- **PyTorch** is selected because the current Ultralytics approach runs on it; it also enables local
  fine-tuning on team data if pretrained classes do not cover the experiment objects.
- **Ultralytics-supported trackers** avoid writing and validating a tracker from scratch while still
  letting the team compare ByteTrack and BoT-SORT through configuration.
- **OpenCV + NumPy** cover all image and box maths with libraries the rest of the pipeline already uses.

### Alternatives Considered

| Area | Alternative | Why Not Used Initially |
|------|-------------|------------------------|
| Detection framework | Detectron2, MMDetection, transformer-based detectors (e.g. RT-DETR), other YOLO implementations | Larger setup / integration effort for a hackathon timeline; Ultralytics already provides detection + tracking + export. No measured comparison has been made. |
| Tracking | Custom IoU / centroid tracker | More code to write and validate; may be revisited if built-in trackers do not meet the project's needs. |
| Tracking | Re-identification trackers (e.g. DeepSORT-style) | Need an extra appearance model (weights to manage offline) and extra compute; not needed until identity switches are observed. |
| Inference runtime | ONNX Runtime / TensorRT / OpenVINO from day one | Adds an export-and-validate step before a baseline exists; planned as a later optimization. |
| Training infrastructure | Cloud training / hosted model APIs | Conflicts with the offline/no-cloud requirement; any training runs locally. |

## CPU / GPU Considerations

### CPU

The prototype must remain able to run Module 02 on a CPU. Potential limitations:

- YOLO inference is likely to be one of the main bottlenecks of the whole pipeline.
- Processing every frame may not be necessary; detection on a subset of frames (with tracking in
  between) is an option to evaluate.
- Model variant (size) and input size may need tuning to trade accuracy against speed.

All of these are decisions to make **from measurements on the demo hardware**.

### GPU

When an NVIDIA GPU and a CUDA-enabled PyTorch build are available, Ultralytics can run inference on it
(`model.device` in `yolo.yaml`), which can speed up YOLO and any later exported TensorRT/ONNX models.
A GPU is **not mandatory**; the module must work with `device: cpu`.

### Hardware Considerations

- Install the PyTorch build (CPU or CUDA) that matches the demo machine.
- Memory use and inference time depend on model variant and input size; record measured values in
  `models/README.md`.
- Runtime performance must be benchmarked on the final demo hardware.

## Offline Compatibility

After the dependencies are installed, model weights are copied into `02_yolo/models/`, and the
configuration is prepared, Module 02 must **not** require:
internet access, cloud inference, external APIs or ground-station connectivity.

- `model.path` must point to an existing **local file**. If Ultralytics is given only a model *name*
  that does not exist locally, it tries to download it. `yolo_loader.py` must check that the file exists
  first and fail with a clear error otherwise.
- Ultralytics may try to fetch helper assets (for example a font used by its own plotting) or check
  packages on first use. Draw debug overlays with OpenCV, run the full module once during setup, and
  then verify it with networking disabled.
- Disable Ultralytics usage-analytics syncing in its settings (`yolo settings sync=False`) so that no
  usage data is sent anywhere.
- Tracker configuration files ship inside the installed package; any optional re-identification weights
  must be stored locally.

## Shared Schemas Used

- Consumes: `FramePacket`
- Produces: `ObjectFrame`, `DetectedObject`, `ReferenceAnchor`
- Enums: `ModuleStatus`

## Configuration

- `configs/yolo.yaml`: `model.*`, `detection.*`, `tracking.*`, `stability.*`, `reference_anchors.*`
- `configs/classes.yaml`: class list and `reference_roles`

All thresholds are `null` placeholders until chosen and validated on the team's own data.

## Dependencies

- Runtime: `ultralytics`, `torch` (CPU or local CUDA build), `opencv-python`, `numpy`, `PyYAML`
  (see [Technology Stack](#technology-stack)).
- Development: `pytest`.
- Future only (not installed for the baseline): ONNX Runtime, TensorRT, OpenVINO.
- `shared/` package.
- No network access at runtime; no automatic model downloads.

## Developer Ownership

| Area | Owner |
|------|-------|
| Module 02 (all folders) | Teammate 2 — YOLO *(name to be filled in by the team)* |

## How to Run Independently

Once implemented, from the repository root:

```bash
python scripts/run_yolo.py
```

Runs Module 01 as the frame source and Module 02 per frame, drawing boxes and `track_id`s on a
**copy** of the frame. A recorded video (`source.type: video`) allows fully offline testing.

## Testing

```bash
python -m pytest 02_yolo/tests
```

| Test file | Covers |
|-----------|--------|
| `test_detection.py` | Filtering, invalid boxes, empty results, missing model file |
| `test_coordinate_restore.py` | Padding cases, edge boxes, invalid boxes, round trip |
| `test_tracking.py` | `track_id` persistence, lost / reacquired, new objects |
| `test_object_frame.py` | Metadata copy, coordinate bounds, shared schema, anchors, stability |

All tests are currently skipped placeholders.

## Integration Contract

- `ObjectFrame.frame_id` and `timestamp_s` are copied **unchanged** from the `FramePacket`.
- All `bbox_xyxy` values are pixels in the **original source frame** (never letterboxed coordinates),
  clipped to `[0, image_width] × [0, image_height]`.
- `image_width` / `image_height` equal the `FramePacket` dimensions.
- `track_id` is persistent for the same physical object while tracked; a reacquired track keeps its id.
- `track_status` is one of `tentative`, `confirmed`, `lost`, `reacquired`.
- `is_stable` is `True` only after multi-frame confirmation.
- `reference_anchors` is empty when no anchor is visible — an anchor is never invented.
- Class names match `configs/classes.yaml`.
- No detections → valid `ObjectFrame` with empty `detections` and `ModuleStatus.NO_DETECTION`.

## Error / Failure Handling

| Failure | Behaviour |
|---------|-----------|
| Model file missing | Clear start-up error; no download attempt |
| Inference exception | `ModuleStatus.ERROR` for that frame; pipeline continues |
| Invalid box (NaN, zero area) | Dropped and counted |
| Reference anchor not visible | Empty `reference_anchors`; Module 03 marks rack reference invalid |
| Track lost | `track_status = "lost"` until removed per config |

## Current Limitations

- Classes are placeholders; the real experiment classes are not yet defined.
- Tracker approach not yet chosen.
- Track-quality definition not yet specified.
- No trained model or measured detection results yet.

## Future Improvements

- Export to an optimized local inference format if needed after measuring runtime on demo hardware.
- Per-class thresholds once evaluation data exists.
- Keypoint-based reference anchors (rack corners) for a more precise rack frame.
