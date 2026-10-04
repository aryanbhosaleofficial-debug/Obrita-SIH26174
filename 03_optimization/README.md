# Module 03 — Optimization Sequence Pipeline

> Implementation status: functional offline baseline. The rule-based temporal layer is
> independently testable and the pose/hand adapters are optional local MediaPipe hooks.

## Purpose

Module 03 turns detected people and objects into human-centred perception features: body pose,
hand landmarks, skeleton, a rack-relative reference frame, motion, hand-object interaction and
gestures. It is split between **two developers** with a single, explicit hand-over packet
(`SpatialFeaturePacket`) between them.

```text
ObjectFrame + FramePacket
        │
        ▼
┌───────────────────────────────┐
│ SPATIAL SECTION (Teammate 3)  │  pose, hands, skeleton, landmarks, rack reference
└───────────────┬───────────────┘
                │ SpatialFeaturePacket   ◄── hand-over contract
                ▼
┌───────────────────────────────┐
│ TEMPORAL SECTION (Teammate 4) │  motion, interaction, temporal, gesture, quality
└───────────────┬───────────────┘
                ▼
     OptimizationOutputPacket
```

## Position in Main Pipeline

```text
01 Perception Core ──FramePacket (via frame buffer)──┐
                                                     ▼
02 YOLO ─────────────ObjectFrame────────────► [03 Optimization] ──OptimizationOutputPacket──┬──► 04 Boundary
                                                                                           └──► 05 Fusion
```

## Responsibilities

### Teammate 3 — Spatial Section

Owns: `input/`, `roi/`, `pose/`, `hands/`, `skeleton/`, `landmarks/`, `reference_frame/`, `spatial_output/`

- Synchronize `ObjectFrame` with the `FramePacket` of the same `frame_id` and validate inputs.
- Generate operator and hand ROIs from Module 02 detections.
- Run pose and hand landmark inference (locally stored MediaPipe-style models).
- Validate landmarks; resolve handedness.
- Build skeleton (bones from connection tables).
- Temporal landmark filtering, smoothing and explicit handling of missing landmarks.
- Relative-depth (pseudo-3D) representation.
- Build the rack/payload reference frame from Module 02 `ReferenceAnchor`s and transform landmarks
  into rack-relative coordinates.
- Publish `SpatialFeaturePacket`.

### Teammate 4 — Temporal Section

Owns: `motion/`, `interaction/`, `temporal/`, `gesture/`, `quality/`, `output/`

- Motion features: joint angles, displacement, velocity, acceleration, direction (rack-relative).
- Hand-object features: distance, association, proximity, interaction candidates.
- Temporal sequence buffering, filtering and multi-frame confirmation.
- Gesture features and recognition.
- Perception quality gate.
- Publish `OptimizationOutputPacket`.

## Non-Responsibilities

- Camera capture, `frame_id`/timestamp assignment (Module 01).
- Object detection, tracking, `track_id` assignment, reference-anchor detection (Module 02).
- Segmentation, contours, chain codes, boundary state (Module 04).
- Final activity decision / HAR classification (Module 05).
- Procedure-step correctness (Procedure FSM).

## Important Scientific Constraints

- **Depth is relative, not metric.** Monocular pose/hand models provide a *relative depth* (`z_rel`).
  Results are described as *relative depth*, *pseudo-3D* or *relative XYZ* — never as metric 3D —
  unless calibrated depth or stereo reconstruction is added later.
- **Orientation is rack-relative.** Directions and orientations are expressed relative to the
  rack/payload reference frame, not camera "up". In microgravity the operator's body orientation
  relative to the camera is not a reliable "up" reference.
- If no valid rack reference exists, rack-relative outputs are marked **invalid**; the module does
  not silently fall back to camera axes (`allow_camera_up_fallback: false`).
- Distances and velocities are in normalized / rack-relative units, not metres, unless calibrated.

## Inputs

| Input | Source | Used by |
|-------|--------|---------|
| `ObjectFrame` | Module 02 | Teammate 3 (ROIs, anchors), Teammate 4 (object boxes for interaction) |
| `FramePacket` (via frame buffer) | Module 01 | Teammate 3 (image for pose/hands) |
| `configs/optimization.yaml` | Repository | Both |
| `configs/camera.yaml` (`mirrored`) | Repository | Teammate 3 (handedness) |
| Pose / hand model files | Local paths in config | Teammate 3 |

## Outputs

| Output | Producer | Consumer |
|--------|----------|----------|
| `SpatialFeaturePacket` | Teammate 3 | Teammate 4 (internal hand-over) |
| `OptimizationOutputPacket` | Teammate 4 | Module 04, Module 05 |
| `ModuleStatus` + timing | Both | Module 01 health monitor |

## Internal Components

| Folder | Owner | Role |
|--------|-------|------|
| `input/` | T3 | `input_synchronizer.py`, `input_validator.py` |
| `roi/` | T3 | `human_roi.py`, `hand_roi.py` |
| `pose/` | T3 | `pose_detector.py`, `pose_validator.py`, `pose_types.py` |
| `hands/` | T3 | `hand_detector.py`, `hand_validator.py`, `handedness.py` |
| `skeleton/` | T3 | `skeleton_builder.py`, `body_connections.py`, `hand_connections.py` |
| `landmarks/` | T3 | `landmark_filter.py`, `landmark_smoother.py`, `missing_landmarks.py`, `relative_depth.py` |
| `reference_frame/` | T3 | `rack_reference.py`, `reference_validator.py`, `coordinate_transform.py`, `orientation.py` |
| `spatial_output/` | T3 | `spatial_packet_builder.py` |
| `motion/` | T4 | `joint_angles.py`, `displacement.py`, `velocity.py`, `acceleration.py`, `motion_direction.py` |
| `interaction/` | T4 | `hand_object_distance.py`, `object_association.py`, `proximity.py`, `interaction_generator.py` |
| `temporal/` | T4 | `sequence_buffer.py`, `temporal_filter.py`, `multi_frame_confirmation.py` |
| `gesture/` | T4 | `gesture_recognizer.py`, `gesture_features.py`, `gesture_labels.py` |
| `quality/` | T4 | `perception_quality_gate.py` |
| `output/` | T4 | `optimization_packet_builder.py` |

## Technology Stack

> This stack is chosen for the **SIH prototype**: offline demonstration, modular development and rapid
> iteration. It does **not** demonstrate spacecraft qualification, radiation tolerance, flight
> certification, real microgravity validation or mission reliability.

Module 03 has two technology stacks, one per developer section. Python is the implementation language
for both.

### Core Technologies

#### 03A — Spatial / Skeleton Section (Teammate 3)

Pipeline: `ObjectFrame + FramePacket → ROI → Pose → Hands → Landmark validation → Skeleton →
Temporal landmark smoothing → Relative depth → Rack reference → Rack-relative transformation →
SpatialFeaturePacket`

| Technology | Purpose | Required / Optional | Why Used |
|------------|---------|---------------------|----------|
| Python 3 | Section implementation | Required | Same language as the rest of the pipeline. |
| MediaPipe (`mediapipe`) | Body landmarks, hand landmarks, handedness | Required for prototype | Runs locally, is lightweight, is easy to prototype with, and returns structured pose/hand landmarks with visibility/presence scores, which makes it suitable for the initial SIH demonstration without building landmark detection from scratch. |
| OpenCV (`opencv-python`) | ROI extraction, BGR→RGB conversion before MediaPipe, coordinate transforms, geometric operations, debug overlays | Required | Same image library as Modules 01/02/04; frames are already NumPy arrays. |
| NumPy | Landmark arrays, vectors, matrix operations, coordinate transforms, distances, angles, reference-frame calculations | Required | The rack-relative geometry layer is plain linear algebra. |
| SciPy (`scipy`) | Signal smoothing (e.g. Savitzky–Golay), extra geometric/numerical utilities | Optional | Only if a needed operation is not simple to do with NumPy/OpenCV. |

> **Depth is not metric.** MediaPipe landmark depth (`z`) must **not** be treated as physically accurate
> metric 3D. It is described as **relative depth**, **pseudo-3D** or **model-relative coordinates**
> unless calibrated depth (depth camera / stereo) is actually added.

#### 03B — Temporal / Gesture / Interaction Section (Teammate 4)

Pipeline: `SpatialFeaturePacket → Motion features → Hand-object features → Temporal sequence →
Gesture recognition → Interaction recognition → Multi-frame confirmation → Quality gate →
OptimizationOutputPacket`

| Technology | Purpose | Required / Optional | Why Used |
|------------|---------|---------------------|----------|
| Python 3 | Section implementation | Required | |
| NumPy | Joint angles, motion vectors, velocity, acceleration, distance, direction, temporal arrays | Required | All 03B features are small-vector arithmetic over landmark coordinates. |
| `collections.deque` (standard library) | Temporal sequence buffers, sliding windows, multi-frame confirmation | Required | `deque(maxlen=N)` is a bounded sliding window with no dependency and no external message broker. |
| Rule-based logic (plain Python) | Gesture / motion primitives (candidates: reach, move, hold, release, rotate, stationary) | Required (baseline approach) | Easy to debug, explainable, fast and suitable for the SIH prototype. The final label set lives in `configs/optimization.yaml`. |
| PyTorch (`torch`) | Learned temporal gesture/HAR classifier | Optional | Only if rule-based features prove insufficient. |
| SciPy (`scipy`) | Smoothing of velocity/acceleration signals | Optional | Only where justified. |
| ONNX Runtime | Optimized inference of an exported learned temporal model | Future | Only after a learned model exists and is validated. |

### Python Libraries

#### 03A — Spatial / Skeleton (Teammate 3)

| Library | Used For | Module Component |
|---------|----------|------------------|
| `mediapipe` | Pose and hand landmark inference, handedness | `pose/pose_detector.py`, `hands/hand_detector.py`, `hands/handedness.py` |
| `cv2` (opencv-python) | ROI cropping helpers, `cvtColor` BGR→RGB, debug drawing | `roi/human_roi.py`, `roi/hand_roi.py`, `pose/pose_detector.py`, `hands/hand_detector.py` |
| `numpy` | Landmark arrays, validation maths, transforms, orientation | `landmarks/*`, `skeleton/skeleton_builder.py`, `reference_frame/*`, `spatial_output/spatial_packet_builder.py` |
| `collections.deque` | Landmark and reference history | `landmarks/landmark_smoother.py`, `landmarks/missing_landmarks.py`, `reference_frame/reference_validator.py` |
| `dataclasses` | Internal helper types | `pose/pose_types.py` |
| `yaml` (PyYAML) | `configs/optimization.yaml` (03A sections) | Loaded once at module start-up and passed to components |
| `scipy` *(optional)* | Smoothing filters | `landmarks/landmark_smoother.py` |

#### 03B — Temporal / Gesture / Interaction (Teammate 4)

| Library | Used For | Module Component |
|---------|----------|------------------|
| `numpy` | Angles, displacement, velocity, acceleration, direction, distances, gesture features | `motion/*`, `interaction/hand_object_distance.py`, `interaction/proximity.py`, `gesture/gesture_features.py` |
| `math` | Scalar angle helpers | `motion/joint_angles.py`, `motion/motion_direction.py` |
| `collections.deque` | Sliding windows, N-of-M confirmation | `temporal/sequence_buffer.py`, `temporal/temporal_filter.py`, `temporal/multi_frame_confirmation.py` |
| `enum` | `InteractionState` usage | `interaction/interaction_generator.py` |
| `yaml` (PyYAML) | `configs/optimization.yaml` (03B sections), gesture labels | `gesture/gesture_labels.py` |
| `torch` *(optional)* | Learned temporal classifier, only if adopted | `gesture/gesture_recognizer.py` |
| `scipy` *(optional)* | Signal smoothing | `motion/velocity.py`, `motion/acceleration.py` |
| `pytest` | Tests (both sections) | `tests/` |

### Rack-Relative Coordinate System

The rack-relative coordinate system is a **project-specific geometry layer** in `reference_frame/`,
implemented with Python, NumPy and OpenCV geometry. Its purpose is:

```text
camera-relative landmarks (original-frame pixels + relative depth)
        ↓   origin + axes from the Module 02 rack/payload ReferenceAnchor
rack/payload-relative representation
```

No robotics framework (e.g. ROS / tf2) is introduced for this; the transformation is a few vector and
matrix operations.

### Rule-Based Gesture Recognition (First Prototype)

Initial gesture/motion primitives use deterministic rules based on distance, velocity, direction, joint
geometry, object association and time. Rules come first because they are easy to debug, explainable,
fast, and enough for an SIH demonstration. A learned temporal model (PyTorch: LSTM, GRU, TCN or a small
Transformer) is considered only if rules prove insufficient on recorded data — not simply because
PyTorch is already installed for Module 02.

### Required Technologies

| Section | Required |
|---------|----------|
| 03A | Python 3, `mediapipe`, `opencv-python`, `numpy`, `PyYAML` |
| 03B | Python 3, `numpy`, `PyYAML`, `collections.deque` (standard library), rule-based logic |
| Both | Development: `pytest` |

### Optional Technologies

| Technology | Section | Use |
|------------|---------|-----|
| SciPy | 03A / 03B | Signal smoothing, numerical utilities, only where NumPy/OpenCV are not enough |
| PyTorch temporal model (LSTM / GRU / TCN / small Transformer) | 03B | Learned gesture/HAR classification if rule-based features are insufficient; requires team-collected labelled data |

### Future Optimization Technologies

| Technology | Section | Use |
|------------|---------|-----|
| ONNX Runtime | 03B | Optimized inference of an exported learned temporal model, after it has been validated |

### Recommended Stack Summary

| Technology | Purpose | Section | Status |
|---|---|---|---|
| Python | Main implementation | 03A + 03B | Required |
| MediaPipe | Pose/hand landmarks | 03A | Required for prototype |
| OpenCV | ROI + coordinate operations | 03A | Required |
| NumPy | Geometry/motion | 03A + 03B | Required |
| `collections.deque` | Temporal buffers | 03B | Required |
| SciPy | Additional numerical/signal processing | 03A/03B | Optional |
| PyTorch | Learned temporal model | 03B | Optional |
| ONNX Runtime | Optimized future inference | 03B | Future |
| pytest | Testing | 03A + 03B | Development |

## Technology Decisions

### Why These Technologies Were Selected

- **MediaPipe (03A)** was selected for the prototype because it provides lightweight offline pose and hand
  landmarks without requiring the team to build landmark detection from scratch.
- **OpenCV + NumPy (03A)** handle ROIs and the rack-relative geometry with libraries already used elsewhere
  in the pipeline.
- **NumPy + `deque` (03B)** are sufficient for motion features and sliding windows; no framework is needed.
- **Rule-based gestures (03B)** keep the first prototype explainable and testable with synthetic inputs.

### Alternatives Considered

| Area | Alternative | Why Not Used Initially |
|------|-------------|------------------------|
| Pose / hands (03A) | YOLO Pose | Would add a second pose model alongside Module 02; its default pretrained models provide body keypoints only, so a separate hand-landmark model would still be needed. |
| Pose / hands (03A) | OpenPose | Heavier installation/build effort and licensing terms to check; not needed for a first prototype. |
| Pose / hands (03A) | MMPose / custom pose model | Higher integration cost; a custom model needs labelled data and training time. |
| Smoothing (03A) | SciPy filters | Kept optional; simple filters can be written with NumPy first. |
| Rack-relative geometry (03A) | ROS / tf2 transform framework | Large framework for what is a small amount of linear algebra. |
| Gestures (03B) | Learned temporal models (LSTM / GRU / TCN / small Transformer) | Need labelled sequence data, training and validation; less explainable. Planned as optional if rules prove insufficient. |
| Temporal buffers (03B) | pandas rolling windows, message brokers | Unnecessary dependencies for fixed-size in-memory windows. |

No alternative is claimed to be worse; none has been benchmarked by the team.

## CPU / GPU Considerations

### CPU

The prototype should remain capable of local CPU operation. Potential limitations:

- **03A:** MediaPipe adds per-frame processing on top of YOLO (Module 02). Running it on the operator ROI
  instead of the full frame, running hand inference only when needed, or processing a subset of frames
  are options to evaluate from measurements.
- **03B:** rule-based features are small NumPy operations over landmark arrays rather than images.
  Their cost must still be measured, not assumed.

### GPU

- **03A:** MediaPipe's Python package runs on the CPU in the default setup; GPU support depends on the
  platform and API, so a GPU must not be assumed for this section.
- **03B:** only an optional learned PyTorch temporal model (or a future ONNX/TensorRT export) would
  benefit from a GPU. The rule-based baseline does not need one.
- A GPU is **not mandatory** for Module 03.

### Hardware Considerations

- The combined cost of Modules 02 and 03 on the same machine determines how many frames can be processed.
- Smoothing introduces lag; its effect must be measured and documented.
- Runtime performance must be benchmarked on the final demo hardware.

## Offline Compatibility

After the dependencies are installed, model files are copied locally, and the configuration is prepared,
Module 03 must **not** require internet access, cloud inference, external APIs or ground-station connectivity.

- If the MediaPipe **Tasks** API is used, its model files (`.task`) must be downloaded during setup,
  stored locally, and referenced by `pose.model_path` / `hands.model_path` in `configs/optimization.yaml`.
  They are never fetched at runtime.
- If the legacy MediaPipe **Solutions** API is used, its models ship inside the installed package.
- Either way, the module must be verified once with networking disabled.
- An optional learned temporal model (03B) is loaded from a local path only.

## Shared Schemas Used

- Consumes: `FramePacket`, `ObjectFrame`
- Internal hand-over: `SpatialFeaturePacket` (with `Landmark`, `HandLandmarks`, `RackReference`)
- Produces: `OptimizationOutputPacket` (with `MotionFeatures`, `InteractionCandidate`, `GestureResult`)
- Enums: `ModuleStatus`, `InteractionState`

Types in `pose/pose_types.py` are internal helpers only; nothing crossing a module boundary may use them.

## Configuration

`configs/optimization.yaml`:

- Teammate 3: `roi`, `pose`, `hands`, `landmarks`, `rack_reference`
- Teammate 4: `motion`, `temporal`, `gesture`, `interaction`, `quality`

All thresholds are `null` placeholders until tuned on demo data.

## Dependencies

- Runtime (03A): `mediapipe` (local model files only), `opencv-python`, `numpy`, `PyYAML`.
- Runtime (03B): `numpy`, `PyYAML` + standard library (`collections.deque`, `math`, `enum`).
- Optional: `scipy` (smoothing / numerical utilities), `torch` (learned temporal model, 03B only).
- Future only: ONNX Runtime (03B).
- Development: `pytest`.
- `shared/` package. No network access at runtime. See [Technology Stack](#technology-stack).

## Developer Ownership

| Section | Owner | Folders |
|---------|-------|---------|
| Spatial | Teammate 3 *(name to be filled in)* | `input/ roi/ pose/ hands/ skeleton/ landmarks/ reference_frame/ spatial_output/` |
| Temporal | Teammate 4 *(name to be filled in)* | `motion/ interaction/ temporal/ gesture/ quality/ output/` |
| Hand-over contract | Both | `shared/schemas/spatial_feature_packet.py` — changes need both owners' review |

Test ownership: T3 → `test_pose.py`, `test_hands.py`, `test_skeleton.py`, `test_reference_frame.py`;
T4 → `test_motion.py`, `test_interaction.py`, `test_gesture.py`; both → `test_optimization_packet.py`.

## How to Run Independently

From the repository root:

```bash
python -m 03_optimization
python -c "import importlib; p=importlib.import_module('03_optimization.pipeline'); print(p.OptimizationPipeline().process(None, 1, 0.0, []))"
```

Teammate 4 can develop against recorded / synthetic `SpatialFeaturePacket`s without waiting for
Teammate 3's models, because the hand-over is a plain shared dataclass.

## Testing

```bash
python -m pytest 03_optimization/tests
```

The baseline can be exercised with `python -m pytest 03_optimization/tests`.
The component-level tests use synthetic inputs; model-backed tests should be run
on a machine with the locally installed MediaPipe package.

## Integration Contract

- `frame_id`, `timestamp_s` copied **unchanged** into both `SpatialFeaturePacket` and `OptimizationOutputPacket`.
- Upstream inputs are paired strictly by `frame_id`.
- Landmark `x_px`/`y_px` are original source-frame pixels; `z_rel` is relative depth.
- `target_track_id` is the operator `track_id` from `ObjectFrame`.
- `InteractionCandidate.object_track_id` refers to a `track_id` present in the same `ObjectFrame`.
- `object_frame` and `spatial` are passed through read-only for Modules 04 and 05.
- `quality_ok == False` always comes with at least one entry in `quality_reasons`.
- Rack-relative values are only produced when `RackReference.is_valid` is `True`.

## Error / Failure Handling

| Failure | Behaviour |
|---------|-----------|
| No operator detection | No pose; `ModuleStatus.NO_DETECTION`; packet still published |
| Low-visibility landmarks | Marked `is_valid = False`; not used for features |
| Short landmark gaps | Interpolated within configured limit, flagged `is_interpolated` |
| Missing reference anchor | `RackReference.is_valid = False`; rack-relative outputs omitted; quality reason recorded |
| Gesture evidence insufficient | `GestureResult.label = "unknown"` |
| Model file missing | Clear start-up error; no download |

## Current Limitations

- Gesture and activity vocabularies are placeholders.
- Monocular input only — no metric depth.
- Operator-selection rule for multiple people not yet defined.
- Smoothing method and its lag not yet chosen/measured.

## Future Improvements

- Calibrated depth or stereo for metric 3D (would require updating terminology and schemas).
- Learned gesture model trained on team-collected data.
- Multi-operator support.
