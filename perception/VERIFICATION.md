# Module 01 architecture repair — verification record

Verified on 2026-10-04 against the working tree based on `d281159`.
This supersedes the earlier combined-pipeline verification record.

## Assessment and decision evidence

The pre-change working tree was clean. Git history showed the numbered team
scaffold (`dbf7876`) followed by the combined perception implementation (`d281159`).
Repository-wide symbol searches and AST/import inspection found the combined
pipeline consumed by examples/tests, while numbered 01–05 processing code was
unimplemented scaffolding. The older ObjectFrame/SpatialFeaturePacket/
OptimizationOutputPacket leaves were not used by an active processing chain.

The decision was documented before implementation: Module 01 is the frame and
shared-contract foundation. Existing inference/optimization algorithms were
relocated into their numbered owners, with compatibility re-exports. No separate
boundary, HAR or FSM algorithm was introduced. See [INTEGRATION.md](INTEGRATION.md).

## Final automated checks

| Exact command | Passed | Failed | Skipped |
|---|---:|---:|---:|
| `.venv/Scripts/python.exe -m pytest tests/perception -q` | 130 | 0 | 0 |
| `.venv/Scripts/python.exe -m pytest -q --tb=short` | 154 | 0 | 120 |
| `python -m pytest -q --tb=short` | 154 | 0 | 120 |

The `.venv` interpreter is Python 3.11.16; shell `python` is Python 3.14.7.
The baseline was 86 perception tests / 110 full-suite passes with 120 skips.
There are 44 added passing perception cases. Existing test functions were checked
against HEAD with AST comparison: none removed. Assertions were updated only for
intentional contract changes (structured diagnostics, healthy optional capability
limits, preserved ambiguity, isotropic units and transition-only LEAVING).
The 120 pre-existing skipped cases remain numbered-module/application scaffold
work; no new perception test is skipped.

Additional commands passed:

```powershell
.venv/Scripts/python.exe -m mypy perception shared integration --follow-imports=silent --ignore-missing-imports --check-untyped-defs
.venv/Scripts/python.exe -m compileall -q perception shared integration yolo optimization boundary 02_yolo 03_optimization 04_boundary examples
git -c core.safecrlf=false diff --check
```

Mypy checked 49 source files. This is the foundation/shared/composition check;
it does not type-check numbered owner implementations reached through dynamic
package paths or third-party internals. A direct mypy attempt on numbered folders
was rejected because their directory names are not Python identifiers; this is
not presented as passing owner-module type coverage. Runtime tests and compilation
cover those owner implementations.

Ruff check and format check passed on all 66 created/modified Python files. The
exact target list is reproducible from the current repair tree:

```powershell
$repairPythonFiles = git ls-files --modified --others --exclude-standard | Where-Object { $_ -like '*.py' -and (Test-Path -LiteralPath $_) }
.venv/Scripts/python.exe -m ruff check $repairPythonFiles
.venv/Scripts/python.exe -m ruff format --check $repairPythonFiles
```

Unrelated teammate files were not formatted. Broad exception catches are limited
to replaceable backend isolation/cleanup and preserve structured failure evidence.
The numbered legacy package's lint naming exception preserves the team directory.

## Reviewer and break-test evidence

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

Existing tests also cover no objects, no hands, one/two hands, geometric clipping,
invalid scores, 50 objects, disappearance, calibration loss/recovery, source/order
errors, resize restoration, CPU retry, perspective and arbitrary-angle manual
calibration, optional injected pose and lifecycle cleanup.
Original M-number labels were not provided; medium issues above are named by topic.

## Actual integration execution

```powershell
.venv/Scripts/python.exe -m examples.perception_demo --frames 8
python -m examples.perception_demo --frames 8
.venv/Scripts/python.exe -m examples.perception_rotation_demo
```

Both eight-frame chain executions produced healthy packets, current ArUco
verification and successful receiving validation:

`FramePacket -> perception.FrameProcessor -> PreparedFrame -> yolo.YoloPipeline
-> ObjectFrame -> optimization.OptimizationPipeline -> OptimizationOutputPacket
(with SpatialFeaturePacket) -> boundary.input.validate_boundary_input`.

The real module/schema/geometry/temporal code ran with synthetic detector/hand
observations injected at backend interfaces. At the end, three confirmed
near/contact-candidate/overlap primitives were present. No boundary segmentation,
BoundaryOutputPacket, HAR activity or procedure outcome was simulated.

A temporary nested verification launcher initially resolved bare `python` to an
interpreter without NumPy. Direct shell execution and rerunning with the explicit
resolved Python path passed; no application code change was needed.

The ArUco example detected all four rotations. Regression tests additionally
verify an OFF-CENTER physical point keeps rack coordinates (.25,.75), preventing
a trivial center-only or camera-axis interpretation from passing.

Stage timings are measured with perf_counter. An illustrative eight-frame
400x400 synthetic/ArUco run had median preprocessing 0.2199 ms, reference detection
2.0536 ms and total 2.6950 ms. These include mocked model stages and are NOT model
inference FPS or target hardware benchmarks. The full JSON trace is locally saved
at `outputs/debug_frames/perception_chain_verification.jsonl` (ignored runtime output).

## Offline checks with real installed backends

```powershell
.venv/Scripts/python.exe -m examples.perception_offline_check mediapipe
python -m examples.perception_offline_check yolo
python -m examples.perception_offline_check yolo --tracking
```

All three final commands passed. The executable installs a Python audit hook
before backend imports and rejects/counts socket.connect, socket.getaddrinfo and
socket.sendto attempts. Each backend processed three blank 320x240 frames with
**zero network attempts**, returned zero observations and closed cleanly.

- MediaPipe 1.0.1 on Python 3.11.16 loaded the existing official local
  `models/hand_landmarker.task` and ran synchronous VIDEO timestamps 0/33/67 ms.
  NumPy 2.4.6 and OpenCV contrib 5.0.0.93 were used. Native TFLite feedback/ROI
  diagnostic messages were printed; initialization/inference succeeded.
- Ultralytics 8.4.165 on Python 3.14.7 used CPU, local model architecture and
  temporary RANDOM weights, with NumPy 2.5.3 / OpenCV 5.0.0.93. Detection mode and
  tracker-enabled mode both ran. The initial tracking smoke found missing `lap`;
  it was added to requirements/startup validation and lap 0.5.13 was installed
  during setup before the successful offline rerun. No trained object quality
  or real-scene identity continuity is claimed from blank frames.
- Model-free chain regression also rejects socket connection attempts and checks
  model reuse/source-image preservation.

These are exercised Python runtime paths, not an OS firewall/native-code network
audit or coverage of every optional platform/backend. No cloud service is used.
The local hand asset and virtual environment are ignored, not committed.

## Final self-review and remaining deployment work

- Existing algorithms were relocated, not duplicated under Module 01. All active
  packet/observation definitions are in shared/schemas. Legacy exports are aliases.
- Original HAR, FSM, procedures, main and script implementations are unchanged.
- Runtime errors remain observable; a missing required model/class mapping fails
  startup. No accuracy is inferred from mocks or untrained weights.
- Experiment YOLO weights and finalized class IDs remain absent. The real demo
  profile deliberately requires these assets, local hand model and visible markers.
- Physical camera/video trials, real rack placement, trained recognition evaluation,
  ambiguous-crossing accuracy and target-device/GPU benchmarking remain unverified.
- Body-pose inference, skeleton/gesture algorithms, boundary analysis, HAR, FSM and
  application GUI/recording remain other owners' work. Optional scaffold fields
  are not claims that these algorithms ran.
- Static calibration cannot detect board/camera motion. Live ArUco requires all
  four markers; fallback is explicitly image-diagonal. Rack units are board-axis
  fractions rather than metric distances. Thresholds are configurable demo values.
- Hand continuity is short term and conservative. Ambiguous crossings restart
  keys; tracker IDs are backend/session dependent, not permanent identities.
- Real backend smoke paths were run in two existing Python environments, not a
  trained full-chain hardware deployment in one certified dependency image.

Module 01 is complete for the documented foundation/integration boundary. The
orientation-aware ground prototype is ready for downstream development; none of
this establishes flight qualification or microgravity robustness.
