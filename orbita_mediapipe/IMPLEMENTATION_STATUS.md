# ORBITA Implementation Status

Audit date: 2026-10-02 (Asia/Calcutta)

Scope: source inspection and attempted executable verification of the customized `orbita_mediapipe/` tree. No functional source files were modified. The only created file is this report.

## Executive Summary

The repository contains a coherent prototype implementation for all four workstreams: 3D pose schemas and transforms, 74-dimensional 3D/temporal features, two-slot short-term tracking, and a PyTorch Bottleneck → ReLU → Bottleneck model with Adam training code. The end-to-end source pipeline is wired for synthetic offline input, camera/video input, logging, and per-person inference.

The audit cannot confirm runtime correctness because the available Windows `python` command is only the Microsoft Store alias (`Python was not found`), so pytest, unittest, compileall, CLI help, and checkpoint loading could not execute. The real MediaPipe Pose Landmarker `.task` asset is also absent. Therefore no requirement is classified as `IMPLEMENTED + TESTED` in this audit. Existing JSONL/CSV files and `.pyc` files are artifacts, not independently reproducible test evidence.

Important limitations found in source:

- The native Pose Landmarker path exists, but its required model asset is missing; the default path is `models/pose_landmarker.task`.
- The offline fallback generates synthetic two-person poses. It is useful for software smoke execution, but is not real project data or model-performance evidence.
- Rack-relative coordinates are produced using default nominal calibration values unless a verified calibration result is supplied; the configuration explicitly says `UNVALIDATED_NOMINAL`.
- Tracking is short-term spatial-temporal slot tracking. It is not biometric or long-term re-identification.
- The 3D visualizer initializes Matplotlib optionally and provides an ASCII summary, but no verified 3D skeleton/trajectory render method or screenshot is present.
- The model checkpoint is a smoke checkpoint; no real-data training, validation, accuracy, or FPS evidence is present.

## Repository Baseline

The actual repository is nested at `SIH26174-AI-Assistant-main/orbita_mediapipe/`. Its top-level tree includes upstream MediaPipe (`mediapipe/`), custom implementation (`orbita_human_activity/`), `checkpoints/`, `output_logs/`, `verify_output_logs/`, `docs/`, `Sources/`, `third_party/`, Bazel/build files, Docker files, and Python dependency files.

The custom package contains 36 Python files excluding `__pycache__`, four YAML configuration files, five test modules, a README, sample output schemas/data, and the following functional areas: `schemas`, `spatial`, `features`, `tracking`, `models`, `training`, and `pipeline`.

Git status could not be obtained: the inspected directory and all checked parents are not Git working trees (`fatal: not a git repository`). Accordingly, there is no verifiable Git change list or commit baseline for this audit.

Configuration inspected:

- `orbita_human_activity/configs/coordinates_config.yaml`: three coordinate spaces, rack transform defaults, calibration state, confidence thresholds.
- `orbita_human_activity/configs/tracking_config.yaml`: two slots, association weights/gates, lifecycle settings.
- `orbita_human_activity/configs/model_config.yaml`: T=30, D=74, bottlenecks 32/16, six classes, Adam settings.
- `orbita_human_activity/configs/activity_classes.yaml`: six named activity classes.
- `orbita_human_activity/requirements.txt`: PyTorch, MediaPipe, OpenCV, NumPy, PyYAML, and Matplotlib.

## Task 1 Status — 3D Spatial Representation

| Requirement | File | Status | Evidence | Missing Work |
|---|---|---|---|---|
| Explicit 3D landmark/person representation | `orbita_human_activity/schemas/spatial_types.py:9-91` | IMPLEMENTED + NOT TESTED | `CoordinateSpace`, `Landmark3D`, and `PersonPose3D` distinguish normalized, MediaPipe-world, and rack-relative coordinates. | Execute schema/runtime tests. |
| MediaPipe Pose Landmarker adapter | `orbita_human_activity/pipeline/pose_adapter.py:16-79`; `spatial/transforms.py:15-123` | BLOCKED BY MODEL ASSET | Native `PoseLandmarkerOptions` uses `num_poses=2` and parses normalized/world landmarks. | Supply and load a real `models/pose_landmarker.task`; run a real inference. |
| Offline pose foundation | `pipeline/pose_adapter.py:81-163` | IMPLEMENTED + NOT TESTED | Synthetic two-person generator emits 33 named landmarks and timestamps. | Execute offline smoke test; label all outputs synthetic. |
| Rack-relative transform | `spatial/coordinate_systems.py:24-75` | IMPLEMENTED + NOT TESTED | Implements `P_rack = R @ (P_cam - T)` and preserves landmark metadata. | Execute transform tests and validate calibration inputs. |
| Calibration solve and RMS gate | `spatial/calibration.py:19-110` | IMPLEMENTED + NOT TESTED | SVD/Kabsch-style rigid transform and 15 mm validity gate are implemented. | Run tests with real calibration observations; document calibration provenance. |
| Rack-relative metric validity | `configs/coordinates_config.yaml`; `spatial/calibration.py` | PARTIALLY IMPLEMENTED | Config says `UNVALIDATED_NOMINAL`; default transform values are present, but no verified rack calibration asset/result exists. | Perform and persist a real fiducial calibration; reject nominal coordinates for physical claims. |
| Roll/Pitch/Yaw only with valid 3D | `features/orientation.py:10-127` | IMPLEMENTED + NOT TESTED | Rejects absent 3D landmarks and computes torso-frame Euler values from 3D joints. | Execute tests and validate axis/sign conventions against a known 3D fixture. |
| Timestamp/frame preservation | `schemas/spatial_types.py:69-78`; `spatial/transforms.py:21-26,111-119` | IMPLEMENTED + NOT TESTED | `timestamp_ms` and `frame_index` are carried into `PersonPose3D`. | Verify monotonicity and source timestamp behavior on real video. |
| 3D visualization | `pipeline/visualizer.py:27-54` | PARTIALLY IMPLEMENTED | Optional Matplotlib 3D axes are initialized; ASCII centroid summaries are available. | Implement/verify actual landmark/trajectory rendering and produce screenshot/video evidence. |

## Task 2 Status — Gesture → 3D Axis → Data Conversion

| Requirement | File | Status | Evidence | Missing Work |
|---|---|---|---|---|
| 3D joint-position conversion | `features/temporal_features.py:42-85` | IMPLEMENTED + NOT TESTED | Builds 13×3 position features from active 3D landmarks. | Execute feature tests. |
| 3D kinematic geometry | `features/kinematics.py:10-126` | IMPLEMENTED + NOT TESTED | Computes angles, distances, and unit direction vectors. | Execute tests with occlusion/degenerate-vector cases. |
| 3D axis/orientation conversion | `features/orientation.py`; `features/temporal_features.py:138-146` | IMPLEMENTED + NOT TESTED | Torso basis and normalized Roll/Pitch/Yaw fields are included only when valid. | Execute and independently validate mathematical conventions. |
| Temporal velocity features | `features/temporal_features.py:86-106,148-158` | IMPLEMENTED + NOT TESTED | Timestamp deltas drive joint and torso velocity features. | Run irregular-timestamp tests; verify units and stale-frame handling. |
| Missingness/confidence representation | `features/temporal_features.py:69-84,115-145`; `schemas/feature_types.py:43-63` | IMPLEMENTED + NOT TESTED | Element-wise mask and aggregate confidence are serialized. | Execute tests and verify downstream model masking. |
| Fixed temporal sequences | `features/temporal_features.py:182-224`; `schemas/dataset_types.py:9-30` | IMPLEMENTED + NOT TESTED | Per-person sliding buffers produce `(T,D)` samples with start/end timestamps. | Execute sequence-window tests and verify no cross-person mixing. |
| Gesture/activity data conversion | `training/dataset.py`; `training/smoke_train.py` | PARTIALLY IMPLEMENTED | Dataset schema and synthetic labels/classes exist; live pipeline defaults every inference window to `IDLE_MONITORING`. | Add an authoritative labeled real-data ingestion path and activity-label provenance. |
| Output serialization | `pipeline/serialization.py:11-66`; `sample_output/` | IMPLEMENTED + NOT TESTED | JSONL feature/prediction and CSV prediction formats are implemented and sample files exist. | Execute logger tests and verify schema against downstream consumers. |

## Task 3 Status — Human 1 / Human 2

| Requirement | File | Status | Evidence | Missing Work |
|---|---|---|---|---|
| Multiple-person detection configuration | `pipeline/pose_adapter.py:16-34` | IMPLEMENTED + NOT TESTED | `num_poses=2` is passed to Pose Landmarker options. | Run with a real multi-person model asset. |
| Separate Human 1 / Human 2 slots | `tracking/identity_policy.py:27-44`; `tracking/tracker.py:12-31` | IMPLEMENTED + NOT TESTED | Stable `HUMAN_1` and `HUMAN_2` slot IDs are allocated independently. | Execute multi-person tests. |
| Spatial-temporal association | `tracking/association.py:33-149` | IMPLEMENTED + NOT TESTED | Cost combines 3D displacement and 2D centroid distance with gating and greedy matching. | Run tests; compare behavior under crossing/ambiguous detections. |
| Persistent IDs through brief misses | `schemas/tracking_types.py:19-68`; `tracking/tracker.py:64-80` | IMPLEMENTED + NOT TESTED | Track lifecycle includes tentative, confirmed, coasting, and deletion. | Execute occlusion and reorder tests. |
| Long-term identity persistence/re-entry | `tracking/identity_policy.py:10-24` | PARTIALLY IMPLEMENTED | Source explicitly limits the design to short-term continuity and says biometric/re-ID is absent. | Define identity scope and add appearance/metadata re-ID if required. |
| Per-person downstream processing | `pipeline/orbita_pipeline.py:65-115` | IMPLEMENTED + NOT TESTED | Each active slot independently receives features, sequences, model inference, and logging. | Execute full two-person smoke run. |

## Task 4 Status — Bottleneck + ReLU + Adam

| Requirement | File | Status | Evidence | Missing Work |
|---|---|---|---|---|
| Bottleneck → ReLU → Bottleneck architecture | `models/bottleneck_network.py:35-119` | IMPLEMENTED + NOT TESTED | Linear 74→32, explicit `nn.ReLU`, dropout, Linear 32→16, and six-class head are defined. | Execute forward/backward tests. |
| Temporal input and missingness masking | `models/bottleneck_network.py:71-102`; `pipeline/orbita_pipeline.py:84-94` | IMPLEMENTED + NOT TESTED | Model accepts `(B,T,D)` and applies masks before pooling/inference. | Execute model/pipeline tests. |
| Adam optimizer training | `training/trainer.py:13-110` | IMPLEMENTED + NOT TESTED | `torch.optim.Adam` is explicitly configured and used for backward/step/checkpointing. | Execute training smoke test and inspect optimizer state. |
| Synthetic training smoke path | `training/smoke_train.py:14-104` | IMPLEMENTED + NOT TESTED | Synthetic dataset, two epochs, validation loop, and checkpoint save are implemented. | Run with a working Python/PyTorch environment. |
| Real labeled model training/evaluation | `training/dataset.py`; `training/smoke_train.py` | BLOCKED BY DATA | Only synthetic sample generation is present in the inspected custom tree. | Provide real labeled recordings, split by session, and run reproducible evaluation. |
| Accuracy/FPS/performance evidence | `output_logs/`; `verify_output_logs/`; `sample_output/` | BLOCKED BY DATA | Existing outputs contain predictions, but no real-data evaluation protocol, metrics, or benchmark evidence. | Generate metrics only from real held-out data and measured hardware runs; do not infer claims from sample logs. |

## Integration Status

| Link | Status | Evidence | Gap |
|---|---|---|---|
| Camera → input frame | IMPLEMENTED + NOT TESTED | `pipeline/orbita_pipeline.py:133-174` uses OpenCV `VideoCapture`; CLI accepts `--camera`. | No live-camera execution or hardware evidence. |
| Video file → input frame | IMPLEMENTED + NOT TESTED | Same `run_video` path accepts a string source; CLI accepts `--video`. | No real video file or execution evidence. |
| Input → MediaPipe Pose Landmarker | BLOCKED BY MODEL ASSET | `pipeline/pose_adapter.py:38-79` creates native Tasks detector when asset exists. | Required `.task` asset absent; native path unverified. |
| Input → offline synthetic pose fallback | IMPLEMENTED + NOT TESTED | `pipeline/pose_adapter.py:81-163`. | Python runtime unavailable for execution. |
| MediaPipe pose → tracking | IMPLEMENTED + NOT TESTED | `orbita_pipeline.py:58-66` sends detections to `MultiPersonTracker`. | No executable integration run. |
| Tracking → 3D pose/features | IMPLEMENTED + NOT TESTED | `orbita_pipeline.py:70-85` processes each active tracked pose. | No executable integration run. |
| Features → temporal sequence | IMPLEMENTED + NOT TESTED | `TemporalSequenceManager.add_frame_feature` is called per person. | No executable integration run. |
| Temporal sequence → model | IMPLEMENTED + NOT TESTED | `orbita_pipeline.py:87-110` tensors the window and runs inference. | Checkpoint loading is not wired into the pipeline; default model is freshly initialized. |
| Model → visualization | PARTIALLY IMPLEMENTED | Tracking overlay exists in `run_video`; `TrajectoryVisualizer3D` provides ASCII only and is not called by the master pipeline. | Connect and verify actual 3D visualization. |
| Pipeline → JSONL/CSV output | IMPLEMENTED + NOT TESTED | `DataLogger` is called for frame features and predictions. | No logger test could execute. |

## Tests

### Tests that pass

None can be reported as passed in this audit because the Python test runner could not start.

### Tests that fail or are blocked

- `python -m pytest orbita_human_activity/tests -q`: blocked before collection; Python is unavailable and resolves to the Microsoft Store alias.
- `python -m compileall -q orbita_human_activity`: blocked by the same Python environment issue.
- `python orbita_human_activity/run_pipeline.py --help`: blocked by the same Python environment issue.
- Checkpoint load inspection: blocked by the same Python environment issue.

### Tests not executed

- The five custom unittest modules contain 16 test methods: spatial/calibration (4), tracking (4), feature extraction (4), model architecture (3), and pipeline smoke (1).
- No direct tests cover serialization, CLI argument behavior, MediaPipe result adaptation, visualizer rendering, calibration configuration loading, or training checkpoint compatibility.

### Integration tests

`tests/test_pipeline_smoke.py` exists and exercises the synthetic pipeline for 35 frames, logging, sequence creation, and predictions, but it was not executed in this environment.

### Live-camera tests

Not executed. No camera hardware evidence is present.

### Real-video tests

Not executed. No non-upstream video fixture was found under the audited custom tree.

### Synthetic-only tests

The pose fallback and `training/smoke_train.py` are synthetic. Existing `output_logs/` and `verify_output_logs/` appear consistent with prior synthetic runs, but their execution provenance cannot be established from source control because no Git repository metadata is present.

## Model Assets

Required/custom assets found:

- **Missing:** `models/pose_landmarker.task`, the default native MediaPipe Pose Landmarker bundle referenced by `run_pipeline.py:16` and `pipeline/orbita_pipeline.py:141-143`.
- **Present:** `checkpoints/smoke_model.pt` (182,435 bytes). It is a PyTorch ZIP-format checkpoint and is identified by source code as a smoke-training output; its metadata could not be loaded because Python is unavailable.
- **Present but unrelated upstream test assets:** multiple `.tflite` files under `mediapipe/**/testdata` and an upstream text test `.pt`. They are not ORBITA pose or HAR model assets.
- **Absent:** custom `.onnx`, `.pth`, `.ckpt`, `.tflite`, or `.task` model assets suitable for the ORBITA pipeline.

## Data Status

| Data category | Status | Evidence |
|---|---|---|
| Real project recordings | MISSING | No audited custom-tree camera/video fixtures or labeled recordings were found. |
| Synthetic data | PRESENT | `training/smoke_train.py` generates synthetic sequences; `pipeline/pose_adapter.py` generates two synthetic poses. |
| Sample data | PRESENT | `orbita_human_activity/sample_output/` contains schema examples, including illustrative predictions. |
| Test fixtures | PRESENT, synthetic | Unit tests construct NumPy landmark/calibration fixtures and the smoke test uses generated poses. |
| Calibration observations | MISSING | Calibration solver and nominal defaults exist, but no real fiducial observation file/result exists. |

No accuracy, FPS, dataset-size, or production-performance claim is supported by the inspected evidence.

## Evidence Status

Present:

- Source-level implementation and five custom test modules.
- `output_logs/CLI_RUN_*` and `verify_output_logs/MULTI_PERSON_VERIFY_*` JSONL/CSV output files.
- `orbita_human_activity/sample_output/*` schema/sample files.
- `checkpoints/smoke_model.pt`.

Not present or not verified:

- No screenshots, rendered 3D visualization, recorded camera/video output, real-data metrics, benchmark logs, calibration report, or test-run transcript.
- Existing output files are not sufficient to prove the current source executed successfully.

## Submission Readiness

### Percentage calculation

The percentages below are **static source implementation coverage**, not runtime confidence or model accuracy. The denominator is the number of atomic requirement rows in the corresponding workstream table. A row counts as complete only when its status is `IMPLEMENTED + TESTED` or `IMPLEMENTED + NOT TESTED`; `PARTIALLY IMPLEMENTED`, `BLOCKED BY ...`, `STUB / PLACEHOLDER`, `MISSING`, and `DOCUMENTATION ONLY` do not count. This is a direct count of implemented rows, so it is reproducible from the tables and intentionally does not hide the untested state.

| Task | Complete implementation rows | Total rows | Static implementation coverage | Execution-verified rows |
|---|---:|---:|---:|---:|
| Task 1 | 6 | 9 | 66.7% | 0 |
| Task 2 | 7 | 8 | 87.5% | 0 |
| Task 3 | 5 | 6 | 83.3% | 0 |
| Task 4 | 4 | 6 | 66.7% | 0 |

The coverage figures are not a claim that the system is operational; all execution-verified counts are zero for this audit because the required Python runtime was unavailable.

### Blockers

- Python/PyTorch/MediaPipe runtime is unavailable through the current environment, preventing all executable verification.
- Native Pose Landmarker `.task` model asset is absent.
- No real labeled project data, real video, or calibration observations are present.
- Git metadata is absent, so changed-file provenance cannot be audited.

### Risks

- Default rack transform is nominal/unvalidated; physical rack-relative accuracy must not be claimed.
- The default pipeline constructs a fresh untrained model rather than loading `checkpoints/smoke_model.pt`.
- The pipeline uses `RunningMode.IMAGE`; timestamp is preserved in ORBITA records, but native detector temporal tracking behavior is not demonstrated.
- Greedy association is documented as minimum-cost matching but is not a Hungarian solver; crossing/ambiguous cases require validation.
- Sample outputs include plausible confidence values, but they are not evaluation evidence.

### Exact next implementation order

1. Restore a supported Python 3.10–3.12 environment and install the package requirements; run all 16 custom tests, compileall, CLI help, and smoke training.
2. Supply the official local Pose Landmarker `.task` asset and run a deterministic native single-person and two-person fixture.
3. Add direct tests for adapter parsing, timestamp monotonicity, serialization, visualizer rendering, configuration loading, checkpoint loading, and real pipeline model selection.
4. Provide real project recordings and session-level labels; implement the authoritative data-ingestion/evaluation path and report held-out metrics only.
5. Perform rack fiducial calibration, persist the verified transform and RMS result, and gate physical-coordinate claims on calibration validity.
6. Validate Human 1/Human 2 identity behavior under crossing, occlusion, exit/re-entry, and more than two detections.
7. Connect a trained checkpoint and actual 3D visualization, then collect reproducible screenshots, videos, logs, and hardware-specific performance measurements.
8. Re-run the full audit from a real Git working tree and record the exact commit, environment, model asset hashes, data split, and test transcript.

