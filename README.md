# SIH26174

**AI Human Activity Recognition for On-board BAS Experiments** — Smart India Hackathon prototype.

> **Status: Modules 01–05 have an executable offline baseline and synthetic integration.**
> Module 01 owns shared contracts and frame preparation. YOLO adapters live in 02;
> hands, calibration and interaction continuity live in 03. Module 04 now runs
> local contours and confirmed STATIONARY/MOVING/CONTACT/SEPARATING evidence.
> Module 05 performs configured rule-based HAR with temporal confirmation.
> Real inference awaits local model assets and a matching class mapping.
> Rack-relative boundary rotation and the wider application remain incomplete.
> See [the milestone repair report](MODULES_01_05_REPAIR.md) for commands and evidence.
> See [perception/INTEGRATION.md](perception/INTEGRATION.md) for the single
> authoritative boundary and [verification evidence](perception/VERIFICATION.md).

Run the model-free stage chain from the repository root:

```bash
python -m pip install -r requirements-perception.txt
python -m examples.perception_demo
python -m pytest tests/perception -q
```

Module 03 now provides confirmed/held object evidence, EMA confidence and bounded
image-free temporal windows through the existing shared output packet. Its
standalone replay requires no detector or hand model:

```bash
python -m optimization.standalone_cli --synthetic
python -m optimization.standalone_cli --input detections.jsonl
```

See [Module 03 documentation](03_optimization/README.md) for the authoritative
temporal API, configuration and tests. Module 04 validates this evidence and
analyzes currently observed stable targets with the original source image.
See [Module 04 runtime and limitations](04_boundary/README.md) and
[recovery evidence](04_boundary/MERGE_REPORT.md). Run its independent offline demo:

```bash
python scripts/run_boundary.py --synthetic --frames 5
```

## Project Overview

An offline AI perception pipeline that watches an operator performing an experiment procedure,
recognizes their activities from camera video, and checks those activities against a configurable
procedure definition (correct step, wrong-order step, skipped step, next-step suggestion).

## Problem Statement

Operators carrying out on-board experiment procedures can perform steps in the wrong order or skip
them. The goal is to recognize human activity (hand/body pose, hand-object interaction, object state)
from video and compare it with the expected procedure, without depending on network connectivity.

## Prototype Scope

**In scope (hackathon prototype):**

- Single fixed camera, recorded or live, on a laptop/desktop-class machine.
- Configurable object classes, gestures, activities and procedures (placeholders for now).
- Detection + tracking, pose/hand landmarks, rack-relative reasoning, boundary analysis, evidence fusion.
- A procedure FSM that reports correct / wrong-order / skipped steps.
- Fully offline runtime.

**Out of scope:** GUI, cloud services, model training pipelines, flight hardware integration.

## Architecture

The current architecture splits the system into five perception modules plus a separate Procedure FSM. Modules talk to each
other **only** through the shared packet schemas in `shared/schemas/`.

| # | Module | Folder | Primary output |
|---|--------|--------|----------------|
| 01 | Perception Core | `perception/` (`01_perception_core/` is a legacy pointer) | `PreparedFrame` |
| 02 | YOLO | `02_yolo/` | `ObjectFrame` |
| 03 | Optimization Sequence | `03_optimization/` | `SpatialFeaturePacket` (internal) → `OptimizationOutputPacket` |
| 04 | Boundary Detection | `04_boundary/` | `BoundaryOutputPacket` |
| 05 | Perception Fusion | `05_perception_fusion/` | `ActivityEvent` |
| — | Procedure FSM | `procedure/` | Step outcome + next-step suggestion |

Every module folder contains `README.md` (scope, contracts, ownership), `PIPELINE.md` (stage-by-stage
ASCII pipeline) and `DEFINITION_OF_DONE.md` (objective completion checklist).

### Numbered module directories

The folders `01_perception_core` … `05_perception_fusion` keep the team's module numbering. Python
identifiers cannot start with a digit, so **these folders cannot be imported with a normal `import`
statement** (e.g. `from 02_yolo import ...` is a syntax error).

- `perception/` implements the Module 01 frame foundation.
- Import-safe `yolo`, `optimization`, and `boundary` packages locate code inside
  numbered owner directories using package paths, without duplicating implementations.
  The same stable locators expose `fusion` and the optional `pose_tracking` helper.
- `shared/` defines all stage packets and observation leaves exactly once.
- Normal imports beginning with a digit remain invalid; contract tests enforce this.

## Main Pipeline

```text
External Camera / Frame Source -> FramePacket (source preserved)
  -> 01 FrameProcessor -> PreparedFrame
  -> 02 YoloPipeline -> ObjectFrame
  -> 03 OptimizationPipeline -> OptimizationOutputPacket
                               (current observations + stable evidence + bounded window)
  -> 04 BoundaryPipeline.process_optimization(packet, source_frame) -> BoundaryOutputPacket
  -> 05 FusionPipeline -> ActivityEvent (unknown/current result + confirmed emission flag)
  -> Procedure FSM [implemented; synthetic event demo]
```

`integration.chain.PerceptionChain` composes 01–03.
`integration.milestone.MilestonePipeline` extends it through actual Module 04
contour processing and Module 05 fusion. The headless runner is
`scripts/run_fusion.py`; `--synthetic` replaces capture/detector/landmark inference
while running the real five module interfaces. Module 04 confirms supported boundary states; see its
[targeted repair report](04_boundary/REPAIR_REPORT.md) for tested behavior.


## Module Ownership

| Module | Owner |
|--------|-------|
| 01 Perception Core | Teammate 1 *(name TBD)* |
| 02 YOLO | Teammate 2 *(name TBD)* |
| 03 Optimization — spatial (`input/ roi/ pose/ hands/ skeleton/ landmarks/ reference_frame/ spatial_output/`) | Teammate 3 *(name TBD)* |
| 03 Optimization — temporal (`motion/ interaction/ temporal/ gesture/ quality/ output/`) | Teammate 4 *(name TBD)* |
| 04 Boundary Detection | Teammate 5 *(to be confirmed)* |
| 05 Perception Fusion | Teammate 6 *(to be confirmed)* |
| Procedure FSM, shared schemas | Team decision *(to be assigned)* |

## Repository Structure

```text
SIH26174/
├── README.md, requirements.txt, .gitignore, main.py
├── configs/               owner configs + baseline fusion rules; classes still need the team's model taxonomy
├── shared/                schemas/ (packet contracts), enums/, utils/
├── 01_perception_core/    camera/ synchronization/ pipeline/ buffering/ tests/
├── 02_yolo/               models/ inference/ preprocessing/ detection/ tracking/ stability/ reference/ output/ tests/
├── 03_optimization/       spatial: input/ roi/ pose/ hands/ skeleton/ landmarks/ reference_frame/ spatial_output/
│                          temporal: motion/ interaction/ temporal/ gesture/ quality/ output/   + tests/
├── 04_boundary/           input/ roi/ preprocessing/ segmentation/ contour/ chain_code/ features/
│                          temporal/ fusion/ quality/ output/ tests/
├── 05_perception_fusion/  input/ evidence/ fusion/ temporal/ har/ tests/
├── procedure/             fsm.py, procedure_loader.py, step_validator.py, next_step.py
├── procedures/            demo_experiment.yaml (example only), README.md
├── data/                  raw/ videos/ annotations/ samples/ (large media not committed)
├── logs/                  runtime logs (not committed)
├── outputs/               recordings/ debug_frames/ events/ (not committed)
├── scripts/               run_camera.py … run_full_pipeline.py
└── tests/                 cross-module contract and integration tests
```

## Shared Data Contracts

All packets are Python dataclasses in `shared/schemas/`:

| Packet | From → To |
|--------|-----------|
| `FramePacket` | External capture → 01; retained source for 03/04 |
| `PreparedFrame` | 01 → 02/03 |
| `ObjectFrame` | 02 → 03 (pass-through to 04, 05) |
| `SpatialFeaturePacket` | 03 spatial → 03 temporal (pass-through to 04, 05) |
| `OptimizationOutputPacket` | 03 → 04, 05 |
| `BoundaryOutputPacket` | 04 → 05 |
| `ActivityEvent` | 05 → Procedure FSM |

Common rules:

- `frame_id` is assigned once by the external source and copied unchanged by every module.
- `timestamp_s` is a monotonic capture time in seconds, copied unchanged.
- Image coordinates are pixels in the **original source frame** (never letterboxed).
- Known confidence values are in `[0.0, 1.0]`; unavailable components are `None`.
- `source_id/session_id` namespace continuity; backend IDs and short-term keys differ.
- Every packet carries a `ModuleStatus`.
- Modules must not redefine their own versions of these packets; contract changes go through `shared/`
  and need review from all affected module owners.

## Technology Stack

| Layer | Primary Technology |
|---|---|
| Language | Python |
| Camera / Vision | OpenCV |
| Object Detection | YOLO / Ultralytics |
| AI Runtime | PyTorch |
| Pose / Hands | MediaPipe |
| Numerical Processing | NumPy |
| Optional Numerical Tools | SciPy |
| Tracking | Configurable ByteTrack / BoT-SORT |
| Boundary Processing | OpenCV + Freeman Chain Code |
| Temporal Buffers | Python `deque` |
| Configuration | YAML / PyYAML |
| Procedure Validation | Python FSM + YAML |
| Testing | pytest |
| Future Edge Runtime | ONNX Runtime / TensorRT / OpenVINO |

The project intentionally starts with simple, explainable and testable technologies before introducing
heavier learned models. Each module README has a **Technology Stack**, **Technology Decisions**,
**CPU / GPU Considerations** and **Offline Compatibility** section that explains what each technology is
used for in that module and which files use it.

### Technology Flow

```text
Camera
  │
  │ OpenCV
  ▼
Perception Core
  │
  ▼
YOLO
Ultralytics + PyTorch + OpenCV
  │
  ▼
ObjectFrame
  │
  ▼
Optimization
MediaPipe + OpenCV + NumPy
  │
  ├──────────────┐
  │              ▼
  │        Boundary Detection
  │        OpenCV + NumPy
  │        + Freeman Chain Code
  │              │
  └──────┬───────┘
         ▼
Perception Fusion
Python + NumPy
+ optional PyTorch HAR
         │
         ▼
ActivityEvent
         │
         ▼
Procedure FSM
Python + YAML
```

### Where Each Technology Lives

| Technology | Modules | Not used in |
|------------|---------|-------------|
| OpenCV | 01, 02, 03A, 04 | 05, Procedure FSM |
| Ultralytics YOLO | 02 only | everywhere else (no YOLO inference outside Module 02) |
| PyTorch | 02 (required, via Ultralytics); 03B and 05 (optional learned temporal models) | 01, 03A, 04 |
| MediaPipe | 03A only | everywhere else |
| Freeman chain code | 04 only | everywhere else |
| NumPy | all modules | — |
| `collections.deque` | 01, 02, 03, 04, 05 (bounded buffers / windows) | — |
| PyYAML | all modules + Procedure FSM | — |

### Required / Optional / Future

| Category | Technologies | When |
|----------|--------------|------|
| **Required** (baseline) | Python, OpenCV, NumPy, PyYAML, Ultralytics, PyTorch, MediaPipe; pytest for development | Needed for the first working prototype; listed in `requirements.txt` |
| **Optional** | SciPy; PyTorch learned temporal HAR / gesture models (03B, 05) | Only if a concrete need appears; not installed by default |
| **Future optimization** | ONNX Runtime, TensorRT, OpenVINO | Only after the baseline pipeline works end-to-end and has been measured |

### Not Used by Design

ROS / ROS2, Kafka, RabbitMQ, Redis, Celery, Docker Swarm, Kubernetes, cloud databases, cloud ML APIs,
microservices and distributed message brokers. The prototype runs on one standalone machine; modules
communicate in-process through typed Python objects, queues and buffers.

### Prototype Stack vs Flight Software

This stack is selected for the **SIH prototype**: offline demonstration, modular development and rapid
iteration. It does **not** demonstrate spacecraft qualification, radiation tolerance, flight
certification, real microgravity validation or mission reliability. Runtime performance of every module
must be benchmarked on the final demo hardware; no performance figures are claimed.

## Configuration

| File | Used by |
|------|---------|
| `configs/camera.yaml` | Future external capture application |
| `configs/perception.yaml` | Module 01 preprocessing only |
| `configs/perception_demo.yaml`, `configs/perception_mock.yaml` | Integration profiles referencing owner configs |
| `configs/yolo.yaml` | Module 02 |
| `configs/optimization.yaml` | Module 03 |
| `configs/boundary.yaml` | Module 04 |
| `configs/fusion.yaml` | Module 05 |
| `configs/classes.yaml` | Modules 02–05 |
| `procedures/*.yaml` | Procedure FSM |

Module 01–03 thresholds are explicit configurable demonstration parameters, not validated physical
constants. Class IDs and wider boundary/fusion settings still contain placeholders. Owner model paths
resolve relative to the owning YAML file; integration profiles contain paths rather than duplicate settings.

## Installation

```bash
python -m venv .venv
# Windows: .venv\Scripts\activate      Linux/macOS: source .venv/bin/activate
pip install -r requirements.txt
```

Setup notes:

- Install PyTorch using the build (CPU or CUDA) that matches the demo machine.
- Use a Python version for which `torch`, `ultralytics` and `mediapipe` publish wheels (check each
  project's install page). Very recent Python releases may not be supported yet.
- `mediapipe` installs its own OpenCV package (`opencv-contrib-python`) as a dependency. If `cv2` imports
  behave oddly because two OpenCV packages are installed, keep only one of them in the environment.
- Optional and future packages (SciPy, ONNX Runtime, OpenVINO, TensorRT) are **not** installed by default;
  see the comments in `requirements.txt`.
- Place model weights in `02_yolo/models/` (not committed) and any MediaPipe Tasks model files at the
  local paths set in `configs/optimization.yaml`.

After installation, the system must run without network access.

## Running Individual Modules

Run from the repository root. Synthetic commands require no camera or model assets.

```bash
python scripts/run_camera.py --synthetic  # capture packets + Module 01 preparation
python scripts/run_yolo.py -h             # Modules 01-02 local image inference options
python scripts/run_optimization.py --synthetic  # Module 03 ObjectFrame replay
python scripts/run_boundary.py --synthetic --frames 5  # standalone Module 04
python scripts/run_fusion.py --synthetic  # genuine Modules 01-05 chain
```

## Running Full Pipeline

```bash
python main.py
# or
python scripts/run_full_pipeline.py
```

These commands demonstrate the existing procedure FSM using scripted events;
they do not perform perception. Use `run_fusion.py` for the five-module milestone.

The deterministic procedure/recovery layer is documented in
[procedure/README.md](procedure/README.md), including the shared event contract,
session isolation, confirmation, recovery policies, GUI/voice sinks and tests.

```bash
python -m procedure.demo --procedure red_yellow_box --scenario all
# Attach the FSM to actual Module 05 outputs with synthetic perception inputs:
python scripts/run_fusion.py --synthetic --procedure procedures/fusion_touch_move.yaml --output outputs/events/fusion-frames.jsonl --events outputs/events/fusion-events.jsonl --guidance outputs/events/fusion-guidance.jsonl
```

The red/yellow sequence uses synthetic recognized activities. The touch/move
configuration uses existing Module 05 labels. Neither is an approved BAS
experiment procedure or flight-certified procedure-management system.

## Testing

```bash
python -m pytest
```

Run with `python -m pytest` from the repository root so that `shared` is importable.

- `tests/test_packet_contracts.py` contains real checks of the shared contracts and of the
  numbered-folder import rule.
- `tests/perception/` exercises active core, owner-stage, backend and reviewer regressions.
- Module 05 and the milestone runner have real unit/integration tests.
- Remaining skips cover unused historical planning interfaces, unsupported optional
  boundary features and absent real inference assets; see the repair report.
- `pytest.ini` uses importlib collection and a generated repository-local temp
  directory (`tests_tmp/pytest`), without IDE PYTHONPATH settings.

## Offline Requirement

- No cloud APIs, remote logging, telemetry or runtime downloads.
- Models (YOLO, pose, hands) are loaded from local files; a missing file is an error, never a download.
- Installation is the only step that needs network access.
- Every module's Definition of Done includes a "runs with networking disabled" check.
- The SIH YOLO wrapper disables its optional semantic worker by default.
  The separate standalone Qwen demo is outside this milestone and explicitly retains
  its existing localhost-service behavior. The milestone never invokes it.
- The detector requires existing local weights, disables Ultralytics auto-install
  and online checks before importing it, and refuses incompatible pre-imported settings.

## Microgravity / Rack-Relative Reasoning

In microgravity there is no reliable "up". The operator may be oriented arbitrarily relative to the
camera, so camera-image "up" is not a meaningful reference.

- Module 03 detects configured ArUco markers, or accepts manual calibration. Module 02 may separately detect rack/context objects.
- Module 03 publishes `ReferenceFrameInfo` (provenance, verification, transform and axes) and expresses landmarks, motion and orientation
  **relative to the rack/payload**.
- Module 04 reserves rack-relative orientation in its packet; that computation
  is not implemented. Image orientation must not be interpreted as physical up.
- If no valid reference exists, rack-relative outputs are marked invalid — there is no silent fallback
  to camera axes.

Depth from a single camera is **relative depth (pseudo-3D)**, not metric 3D. Distances and velocities
are in normalized / rack-relative units unless calibrated depth or stereo is added.

## Demo Assumptions

### Hackathon prototype assumptions

- One camera with a stable view of the operator and the rack/payload area.
- Ground-based demo setup with normal gravity, simulating an on-board scenario.
- Laptop/desktop hardware; runtime performance will be measured on that hardware, not assumed.
- Baseline activity rules are configured; model-specific object classes and the real
  experiment procedure still need to be supplied by the team.
- One operator and one target object at a time.
- Lighting and backgrounds controlled enough for colour-based segmentation.

### Actual spacecraft / flight-certified requirements (NOT addressed by this prototype)

- Flight-qualified, radiation-tolerant hardware and certified software processes.
- Formal verification & validation, safety and reliability analysis.
- Real on-board experiment procedures and objects defined by the mission.
- Operation in actual microgravity with free-floating operators and objects.
- Crew privacy, data-handling and mission-specific integration requirements.

**This prototype is not flight-ready and makes no flight-readiness claims.**

## Known Limitations

- Modules 01–05 have a verified synthetic baseline. GUI/streaming/final application
  orchestration are outside this milestone.
- Trained experiment YOLO weights, real-scene evaluation and target-hardware performance evidence are absent.
- Monocular camera: relative depth only.
- Colour segmentation is sensitive to lighting.
- Numbered owner code is exposed through import-safe package locators; packaging outside the repository is not configured.
- Procedure definitions are examples, not real experiment procedures.
