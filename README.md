# SIH26174

**AI Human Activity Recognition for On-board BAS Experiments** — Smart India Hackathon prototype.

> **Status: repository scaffold.** Module structure, shared data contracts, configuration
> placeholders and documentation exist. The perception algorithms are **not implemented yet**.
> No accuracy, FPS or latency figures exist for this project yet, and none are claimed.

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

The system is split into five perception modules plus a separate Procedure FSM. Modules talk to each
other **only** through the shared packet schemas in `shared/schemas/`.

| # | Module | Folder | Primary output |
|---|--------|--------|----------------|
| 01 | Perception Core | `01_perception_core/` | `FramePacket` |
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

- In this scaffold they are organizational module containers; no code imports them.
- `shared/` is the only normally importable package used across modules.
- The final loading strategy (e.g. `importlib` by path, or an import-safe package added later) is an
  **open integration decision**. Folders must not be renamed without team agreement.
- `tests/test_packet_contracts.py` fails if any file adds a `from 0X_...`/`import 0X_...` statement.

## Main Pipeline

```text
Camera
   │
   ▼
01 — Perception Core ──────────────── FramePacket (source image via frame buffer) ──┐
   │                                                                               │
   ▼                                                                               │
02 — YOLO ── ObjectFrame                                                           │
   │                                                                               │
   ▼                                                                               │
03 — Optimization Sequence  ◄──────────────────────────────────────────────────────┤
   │   Teammate 3 (spatial) ── SpatialFeaturePacket ──► Teammate 4 (temporal)       │
   │                                                                               │
   ├──────────────┐                                                                │
   │              │                                                                │
   ▼              ▼                                                                │
Optimization   04 — Boundary Detection  ◄──────────────────────────────────────────┘
Packet             │
   │               ▼
   │         Boundary Packet
   │               │
   └───────┬───────┘
           ▼
05 — Perception Fusion
           │
           ▼
     Activity Event
           │
           ▼
     Procedure FSM ──► correct / wrong-order / skipped step, next-step suggestion
```

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
├── configs/               camera / yolo / optimization / boundary / fusion / classes (YAML placeholders)
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
| `FramePacket` | 01 → 02, 03, 04 |
| `ObjectFrame` | 02 → 03 (pass-through to 04, 05) |
| `SpatialFeaturePacket` | 03 spatial → 03 temporal (pass-through to 04, 05) |
| `OptimizationOutputPacket` | 03 → 04, 05 |
| `BoundaryOutputPacket` | 04 → 05 |
| `ActivityEvent` | 05 → Procedure FSM |

Common rules:

- `frame_id` is assigned once by Module 01 and copied unchanged by every module.
- `timestamp_s` is a monotonic capture time in seconds, copied unchanged.
- Image coordinates are pixels in the **original source frame** (never letterboxed).
- Confidence values are in `[0.0, 1.0]`.
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
| `configs/camera.yaml` | Module 01 |
| `configs/yolo.yaml` | Module 02 |
| `configs/optimization.yaml` | Module 03 |
| `configs/boundary.yaml` | Module 04 |
| `configs/fusion.yaml` | Module 05 |
| `configs/classes.yaml` | Modules 02–05 |
| `procedures/*.yaml` | Procedure FSM |

Thresholds and tuning values are `null` placeholders. They must be chosen and validated on the team's
own demo setup; none of them is a validated value yet. Paths are relative to the repository root.

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

Run from the repository root (each script is currently a placeholder that exits with a non-zero status):

```bash
python scripts/run_camera.py         # Module 01
python scripts/run_yolo.py           # Modules 01-02
python scripts/run_optimization.py   # Modules 01-03
python scripts/run_boundary.py       # Modules 01-04
python scripts/run_fusion.py         # Modules 01-05
```

## Running Full Pipeline

```bash
python main.py
# or
python scripts/run_full_pipeline.py
```

Both are placeholders until the modules are implemented.

## Testing

```bash
python -m pytest
```

Run with `python -m pytest` from the repository root so that `shared` is importable.

- `tests/test_packet_contracts.py` contains real checks of the shared contracts and of the
  numbered-folder import rule. These pass on the scaffold.
- All other tests are **skipped placeholders** that list the cases to implement. They are skipped,
  not faked; removing the skip marker makes them fail until implemented.

## Offline Requirement

- No cloud APIs, remote logging, telemetry or runtime downloads.
- Models (YOLO, pose, hands) are loaded from local files; a missing file is an error, never a download.
- Installation is the only step that needs network access.
- Every module's Definition of Done includes a "runs with networking disabled" check.
- Disable Ultralytics usage-analytics syncing (`yolo settings sync=False`) and run every module once
  during setup, so that any first-use asset fetches happen before the offline check.

## Microgravity / Rack-Relative Reasoning

In microgravity there is no reliable "up". The operator may be oriented arbitrarily relative to the
camera, so camera-image "up" is not a meaningful reference.

- Module 02 detects rack/payload **reference anchors**.
- Module 03 builds a `RackReference` (origin + axes) and expresses landmarks, motion and orientation
  **relative to the rack/payload**.
- Module 04 measures boundary orientation relative to the same reference.
- If no valid reference exists, rack-relative outputs are marked invalid — there is no silent fallback
  to camera axes.

Depth from a single camera is **relative depth (pseudo-3D)**, not metric 3D. Distances and velocities
are in normalized / rack-relative units unless calibrated depth or stereo is added.

## Demo Assumptions

### Hackathon prototype assumptions

- One camera with a stable view of the operator and the rack/payload area.
- Ground-based demo setup with normal gravity, simulating an on-board scenario.
- Laptop/desktop hardware; runtime performance will be measured on that hardware, not assumed.
- Placeholder object classes, gestures, activities and procedures defined by the team.
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

- Scaffold only: no perception algorithm is implemented yet.
- No trained models, datasets or measured results exist in this repository yet.
- Monocular camera: relative depth only.
- Colour segmentation is sensitive to lighting.
- The import/loading strategy for numbered module folders is still to be decided.
- Procedure definitions are examples, not real experiment procedures.
