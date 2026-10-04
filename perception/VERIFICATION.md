# Module 01 verification record

Checked on 2026-10-04. This record describes implementation/contract checks,
not recognition accuracy, latency/FPS benchmarking or flight qualification.

## Executed checks

* `python -m pytest tests/perception -q`: **86 passed** on Python 3.14.7.
* `.venv/Scripts/python.exe -m pytest tests/perception -q`: **86 passed** on
  Python 3.11.16.
* `python -m pytest -q`: **110 passed, 120 skipped**. The 120 skipped tests
  predate this implementation and remain other scaffold/application tests;
  none of the Module 01 perception tests is skipped.
* `.venv/Scripts/python.exe -m pytest -q`: **110 passed, 120 skipped**;
  same full repository suite on Python 3.11.16.
* `python -m compileall -q perception shared/schemas/perception_frame_result.py examples`:
  passed.
* Ruff check/format of `perception`, its new shared schema, examples and tests:
  passed. No unrelated Python module was formatted.
* `mypy perception shared/schemas/perception_frame_result.py --follow-imports=silent
  --ignore-missing-imports --check-untyped-defs`: passed, 17 source files.
  Third-party missing stubs are ignored; model-specific runtime objects remain
  inside adapters, while their public outputs are typed dataclasses.
* `python -m examples.perception_demo --frames 8` and the Python 3.11 invocation:
  successful structured JSON simulation. Objects became stable on frame ID 2;
  near/contact/overlap candidates first appeared on frame ID 3 with four
  observations and original confidence components. The eight-frame output
  retained frame IDs, monotonic timestamps and valid synthetic rack coordinates.

## Real library smoke checks

* MediaPipe **1.0.1**, Python **3.11.16**, NumPy **2.4.6**, OpenCV contrib
  **5.0.0.93**: inspected installed `HandLandmarkerOptions`, `detect` and result
  fields. Loaded the official local `models/hand_landmarker.task`, processed
  a 320x240 black uint8 frame, returned zero hand observations and closed cleanly.
  Tasks emitted its own TensorFlow Lite feedback/projection diagnostics; these
  did not prevent initialization or inference. Public output conversion is
  separately tested with scripted 21-landmark/handedness Tasks results.
* Ultralytics **8.4.165**, Python **3.14.7**, NumPy **2.5.3**, OpenCV
  **5.0.0.93**: created a YOLO11 nano network from the installed local YAML,
  saved **untrained temporary weights**, loaded those through the adapter on CPU,
  processed a black 320x240 frame, returned zero object observations and closed.
  Temporary weights were removed; they are not experiment-object models.
* Repeated both real-library smoke checks while `socket.socket.connect` was
  replaced with a rejecting function: **zero socket connection attempts**.
  YOLO was launched with `YOLO_AUTOINSTALL=false` and `YOLO_OFFLINE=true`.
  This verifies the exercised local inference path; it is not a network audit
  of every optional third-party backend/platform path.

The Python 3.11 `.venv` and downloaded hand model are local, ignored assets.
Optional inference dependencies and the MediaPipe model were acquired during
setup; module runtime does not acquire them.

## Requirement-to-evidence audit

| Requirement/deliverable | Authoritative implementation and verification |
|---|---|
| Architecture, folder structure, scope and limitations | `README.md`, `INTEGRATION.md`; preserved numbered scaffold; root/Module 01 notices |
| Complete Python implementation | `perception/*.py`; compile, lint, type check and exercised mock/real adapter paths |
| Input and type-safe output contracts | Reused `shared/schemas/frame_packet.py`; new `perception_frame_result.py`; shared contract suite and pipeline identity tests |
| Configuration YAML and validation | `config.py`, three `configs/perception*.yaml`; 19 config tests, including relative paths, bad keys/ranges/types/calibration |
| Preprocessing, source metadata and restoration | `preprocessing.py`; resizing/rounding, RGB/BGR, copy preservation, invalid arrays/metadata tests |
| Detector abstraction, filtering, YOLO integration | `detector.py`; raw result conversion, whitelist/threshold/clipping/IDs, missing model, CPU retry/device and tracking safety tests; real CPU smoke |
| Hand adapter and optional pose interface | `hand_tracker.py`, `pose_tracker.py`; Tasks option/RGB/pixel/score tests, tracker failure and injected pose pipeline test; real Tasks smoke |
| Coordinate frames and rack orientation | `coordinate_frame.py`; normalized conversion, perspective, 0/90/180/37/-64 degree transforms, invalid calibration/invalidation tests |
| Interaction geometry and primitives | `associations.py`, `interaction.py`; point/box/polygon distance, IoU, containment, near/far, multiple hands/objects, ambiguity, leaving and confidence tests |
| Stabilization, dropout and confidence handling | `stabilizer.py`; single false positive, consecutive confirmation, tolerated dropout with no stale output, expiry, tentative dropout, ambiguous continuity and capped EMA tests |
| IDs, motion and trends | Persistent vs ephemeral contract fields; no-ID confirmation, unknown motion without track/calibration, tracked rack velocity and approach/retreat tests |
| Main pipeline and ordinary failures | `pipeline.py`; valid/empty/invalid frames, detector/hand/reference exceptions, partial transform failure, calibration loss/recovery, source/order/gap handling |
| Lifecycle and worker use | Lock/initialize/close/reset methods; initialization rollback, idempotent close and stream reset tests; no created processing thread |
| Timings and optional visualization | Stage timing/result fields and `visualization.py`; nonnegative/bounded timings and copy-only overlay tests |
| Mock backends and integration example | `mocks.py`, `examples/perception_demo.py`; eight-frame structured simulation and model-free integration suite |
| Small real capture example | `examples/perception_camera.py`; external capture ownership, monotonic source packet creation and finally-release; compilation (no physical camera tested) |
| Dependencies and public API documentation | Both standalone requirements files; README installation, model placement, API, configuration, coordinate/stabilization instructions |
| Integration contract for Module 02 | `INTEGRATION.md`, `integration.py`; bridge preserves source geometry/time/IDs/status and never fabricates rack anchors |

## Self-review invariants

* No GUI imports, UI update calls, procedure rules, FSM or semantic HAR classifier.
* No `VideoCapture`/`imshow` in the core; capture appears only in the external example.
* No YOLO/MediaPipe result objects in public contracts and no global model instance.
* Valid rack-relative coordinates or an explicit unavailable warning; no physical-up rule.
* Missing hands/objects and model/runtime failures have defined behavior.
* Confirmation exists; stale observations are not presented as current.
* Persistent IDs and unknown confidence components are not fabricated.
* Mocks and tests run without camera, trained YOLO weights or inference libraries.
* YAML owns configuration, runtime observations own warnings and external logging owns persistence.
* No module cloud service/client dependency. Local inference smoke passed with sockets rejected.

## Remaining deployment assets and deliberately optional work

The **implementation** is complete for the requested prototype scope. The team
still needs experiment-specific YOLO weights, measured physical rack calibration,
real-scene evaluation and target-hardware benchmarking before a real demonstration.
Body-pose inference and live marker calibration are documented optional injection
interfaces. Other modules' existing camera/orchestration/HAR/FSM placeholders are
outside this task and were not implemented. The prototype does not establish
microgravity robustness, actual contact/manipulation, spacecraft safety or flight readiness.
