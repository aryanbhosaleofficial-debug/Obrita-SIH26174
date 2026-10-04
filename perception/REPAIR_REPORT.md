# SIH26174 / ORBITA — Module 01 completion report

## 1. Architecture decision

Module 01 is the shared frame/contract foundation:

```text
External frame source -> FramePacket
  -> 01 perception.FrameProcessor -> PreparedFrame
  -> 02 yolo.YoloPipeline -> ObjectFrame
  -> 03 optimization.OptimizationPipeline -> OptimizationOutputPacket
     (SpatialFeaturePacket + canonical observation leaves)
  -> 04 boundary input validation -> team boundary algorithms [scaffold]
  -> HAR [scaffold] -> FSM [scaffold]
```

[INTEGRATION.md](INTEGRATION.md) defines ownership, inputs/outputs, units, identity,
status, serialization and migration. Existing YOLO/hands/geometry/temporal code
was relocated into numbered owners. The `perception/` compatibility modules
re-export those owners and contain no second algorithm. Shared leaves are defined
once; inactive scaffold constructors intentionally migrate to canonical classes.
Application composition lives in `integration/chain.py`.

## 2. Files changed

The complete inventory below is relative to baseline d281159. The working tree
was initially clean. Model weights and runtime JSON traces are ignored assets.

### CREATED (38)

- `02_yolo/inference/class_map.py`
- `02_yolo/inference/detector.py`
- `02_yolo/pipeline.py`
- `03_optimization/hands/hand_tracker.py`
- `03_optimization/interaction/associations.py`
- `03_optimization/interaction/primitives.py`
- `03_optimization/pipeline.py`
- `03_optimization/pose/pose_tracker.py`
- `03_optimization/reference_frame/coordinate_frame.py`
- `03_optimization/temporal/stabilizer.py`
- `04_boundary/input/contract_validator.py`
- `boundary/__init__.py`
- `configs/optimization_mock.yaml`
- `configs/perception_demo.yaml`
- `configs/yolo_mock.yaml`
- `configs/yolo_tracker.yaml`
- `examples/perception_offline_check.py`
- `examples/perception_rotation_demo.py`
- `integration/__init__.py`
- `integration/chain.py`
- `integration/configuration.py`
- `integration/legacy.py`
- `integration/marker_scene.py`
- `integration/mocks.py`
- `integration/visualization.py`
- `optimization/__init__.py`
- `perception/REPAIR_REPORT.md`
- `perception/core.py`
- `shared/config.py`
- `shared/diagnostics.py`
- `shared/errors.py`
- `shared/geometry.py`
- `shared/schemas/observations.py`
- `shared/schemas/prepared_frame.py`
- `shared/utils/observation.py`
- `tests/perception/test_integration_break_cases.py`
- `tests/perception/test_review_regressions.py`
- `yolo/__init__.py`

### MODIFIED (57)

- `01_perception_core/DEFINITION_OF_DONE.md`
- `01_perception_core/PIPELINE.md`
- `01_perception_core/README.md`
- `01_perception_core/__init__.py`
- `02_yolo/DEFINITION_OF_DONE.md`
- `02_yolo/PIPELINE.md`
- `02_yolo/README.md`
- `03_optimization/DEFINITION_OF_DONE.md`
- `03_optimization/PIPELINE.md`
- `03_optimization/README.md`
- `04_boundary/README.md`
- `04_boundary/input/input_validator.py`
- `README.md`
- `configs/camera.yaml`
- `configs/optimization.yaml`
- `configs/perception.yaml`
- `configs/perception_mock.yaml`
- `configs/perception_tracker.yaml`
- `configs/yolo.yaml`
- `examples/perception_camera.py`
- `examples/perception_demo.py`
- `models/README.md`
- `perception/INTEGRATION.md`
- `perception/README.md`
- `perception/VERIFICATION.md`
- `perception/__init__.py`
- `perception/associations.py`
- `perception/config.py`
- `perception/contracts.py`
- `perception/coordinate_frame.py`
- `perception/detector.py`
- `perception/hand_tracker.py`
- `perception/integration.py`
- `perception/interaction.py`
- `perception/mocks.py`
- `perception/pipeline.py`
- `perception/pose_tracker.py`
- `perception/preprocessing.py`
- `perception/stabilizer.py`
- `perception/utils.py`
- `perception/visualization.py`
- `requirements-perception-inference.txt`
- `requirements-perception.txt`
- `requirements.txt`
- `shared/enums/module_status.py`
- `shared/schemas/__init__.py`
- `shared/schemas/frame_packet.py`
- `shared/schemas/object_frame.py`
- `shared/schemas/optimization_packet.py`
- `shared/schemas/perception_frame_result.py`
- `shared/schemas/spatial_feature_packet.py`
- `tests/perception/test_adapters.py`
- `tests/perception/test_associations.py`
- `tests/perception/test_config.py`
- `tests/perception/test_interaction_primitives.py`
- `tests/perception/test_pipeline.py`
- `tests/perception/test_stabilizer.py`

### REMOVED (0)

None. Existing implementation files became compatibility shims after relocation.

### UNCHANGED

- `05_perception_fusion/`, `procedure/`, `procedures/`, `main.py`, `scripts/`.
- Existing inactive YOLO/optimization algorithms and scaffold tests, except the
  explicitly listed receiving validator and documentation files.
- Project class IDs in `configs/classes.yaml` remain team placeholders. No fake
  trained weights, HAR, boundary analysis, GUI or FSM implementation was added.

## 3. Reviewer issues

| Issue | Status | Observable evidence |
|---|---|---|
| H1 competing ownership/contracts | FIXED | `FrameProcessor` imports without inference/optimization; shared aliases are the same classes; real stage packets reach Module 04 receiving validation |
| H2 permanent degradation | FIXED | R01 has None hand confidence, no object tracker ID and nonpersistent hands, yet OK + serialized reliability after confirmation; notices are separate |
| H3 nested/enclosing boxes | FIXED | R02 rack + board + vial/tool retain interactable candidates; equally plausible objects retain ambiguous candidates |
| H4 stale LEAVING | FIXED | R03 emits one recent near-to-far edge, never late; near re-entry rearms; temporary disappearance is timestamp bounded |
| H5 continuity/persistence | FIXED | R05 reorder/disappearance retains short-term keys; ambiguous crossing starts new marked keys; tracker-enabled adapter preserves supplied IDs, disabled mode returns None |
| H6 calibration provenance | FIXED | R06 static calibration remains valid but unverified after image rotation; real ArUco pixels verify each current frame and invalidate on loss |
| FPS-dependent trend | FIXED | R07 equivalent motion at two sampling rates produces equal distance/second |
| Anisotropic fallback / unit thresholds | FIXED | R04 landscape, portrait, 90-degree rotation have equal displacement geometry; rack/image-diagonal thresholds tested separately |
| Dropped/invalid frames | FIXED | R08 retains established continuity over one malformed frame; long valid-frame gaps reset even after malformed input; explicit drop counts do not double count ID gaps |
| NumPy frame IDs | FIXED | R09 accepts np.int64 and publishes a built-in int |
| MediaPipe video/time/handedness | FIXED | VIDEO initialization, ms progression, rejection of nonadvancing ms, missing handedness, mirrored metadata, RGB conversion and optional scores tested |
| Detector class/config validation | FIXED | Wrong class metadata fails on repeated initialization; invalid/duplicate/null classes and out-of-map whitelist fail; missing local tracker dependency fails before inference |
| Confidence/reliability serialization | FIXED | Unknown remains null, measured zero stays zero, raw components and explicit reliability survive JSON serialization |
| Runtime failure recovery | FIXED | Temporary object/tracker and hand failures degrade/fail explicitly, emit no stale interaction, and recover; mismatched stage metadata and mixed units reject |
| Performance/ownership hygiene | FIXED for identified overhead | Source preserved; one backend initialization per continuous stream; source copies limited to preparation; contours/hand boxes cached per association call; bounded histories and measured stage timings |


Original M-number labels were not supplied; remaining issues use descriptive names.

## 4. Tests and checks

| Command | Passed | Failed | Skipped |
|---|---:|---:|---:|
| `.venv/Scripts/python.exe -m pytest tests/perception -q` | 130 | 0 | 0 |
| `.venv/Scripts/python.exe -m pytest -q --tb=short` | 154 | 0 | 120 |
| `python -m pytest -q --tb=short` | 154 | 0 | 120 |

The 120 skips are unchanged scaffold work; all 86 prior perception cases remain,
with 44 additional passing cases. No existing test function was deleted. Ruff
check/format passes for 66 touched Python files. Compileall passes. Mypy passes
for 49 foundation/shared/composition files with its documented scope limitation.
Exact commands, environment versions and detailed evidence are in
[VERIFICATION.md](VERIFICATION.md).

## 5. Integration verification

Both installed Python interpreters ran `-m examples.perception_demo --frames 8`.
All eight frames followed the real 01→02→03→04 receiving-contract path, had OK
status, current ArUco verification, and passed Module 04 validation. The final
frame contained three confirmed geometric candidates. Backend observations were
synthetic; the module stages, contracts, geometry, histories and validator were
real. No BoundaryOutputPacket or HAR/FSM result was invented.

`-m examples.perception_rotation_demo` passed 0/90/180/270 degrees. Actual generated
marker pixels were detected; regression tests verify an off-center physical point
and marker loss as well as the board center.

## 6. Offline verification

The model-free chain rejects sockets in regression tests. Real MediaPipe VIDEO
with the local hand task and real Ultralytics CPU detection/tracker-enabled
inference with temporary untrained local weights each processed three frames
under Python network audit hooks, with **zero network attempts**. Tracking initially
exposed missing lap; setup requirements and startup validation were repaired and
lap 0.5.13 installed before the successful offline run. Dependencies/assets must
be installed beforehand. This is exercised-path verification, not a native-code
network audit or recognition benchmark.

## 7. Remaining limitations

- Experiment-trained YOLO weights/final class IDs, real camera trials, recognition
  accuracy and target-hardware/GPU performance remain unverified.
- Real backend smoke used separate existing Python environments and blank frames;
  it does not prove full trained deployment or real-scene tracking accuracy.
- Body pose/skeleton/gesture, boundary analysis, HAR, FSM and GUI/application work
  remain with their module owners. Their scaffold skips are not completion claims.
- Static calibration cannot detect movement. ArUco needs all four visible markers.
  Distances are board-axis fractions or image-diagonal units, not metric depth.
- Confirmation counts and the 500 ms LEAVING window are configurable demo settings.
  Ambiguous crossings restart continuity; tracker IDs are not permanent identities.
- Dynamic numbered package locators need packaging work if deploying outside this
  source-tree layout; the documented repository-root execution works now.

This is an orientation-aware offline ground prototype, with no flight or
microgravity-validation claim.

## 8. Final decision

```text
MODULE 01 STATUS:
COMPLETE

ARCHITECTURE CONFLICT RESOLVED:
YES

ALL CRITICAL/HIGH REVIEW ISSUES RESOLVED:
YES

REGRESSION TESTS PASS:
YES

OFFLINE OPERATION VERIFIED:
YES

READY FOR NEXT MODULE INTEGRATION:
YES
```

Completion is scoped to the authoritative Module 01 foundation and the exercised
integration boundary, with the deployment limitations above explicit.
