# Module 02 minor-fix repair report

Date: 2026-10-04. Baseline: e33b21b (Module 02); working tree was clean.
Overall status: **READY FOR FINAL REVIEW**.

All eight reviewer findings were independently checked. Four Medium findings are
resolved with targeted changes; safe Low fixes are implemented. Native inference
is not verified in this environment. Final trained weights/class IDs remain
external deployment deliverables and do not block unit-level review readiness.

The earlier implementation report is preserved in Git at e33b21b. This report
supersedes its current behavior/test-count statements; it does not reuse old
verification results. No dependency policy change, model addition, Module 01
algorithm change, Module 03 algorithm change or shared packet shape change occurred.

## Architecture after repair

```text
External FramePacket -> Module 01 FrameProcessor -> canonical PreparedFrame
 -> Module 02 YoloPipeline
    -> existing local backend/model-specific adaptation
    -> parse/filter/validate prepared-pixel observations
    -> PreparedFrame.source_detection() once
    -> source-bound roundoff correction (no second scaling)
 -> canonical original-pixel ObjectFrame
 -> Module 03 OptimizationPipeline -> OptimizationOutputPacket
```

**No architectural boundary change.** Shared definitions remain:
PreparedFrame in shared/schemas/prepared_frame.py, ObjectFrame in
shared/schemas/object_frame.py, Detection/BoundingBox in
shared/schemas/observations.py. Source metadata is unchanged. Offline guards,
local weights, empty results, lazy one-time model loading and backend isolation
remain intact.

## M02-R01 - MEDIUM - FIXED

Classification: MODULE 02 LOCAL FIX + CONFIG CHANGE / INTEGRATION OWNER SIGN-OFF.

Evidence: configs/yolo.yaml had tracking=true and confidence_threshold=0.50;
configs/yolo_tracker.yaml had new_track_thresh=0.60. Installed Ultralytics 8.4.165
byte_tracker.py separates high scores with >= track_high_thresh and does not
start unmatched tracks below new_track_thresh. trackers/track.py retains raw
results when zero tracks return but selects tracker rows when tracks exist,
confirming the reported state-dependent result semantics. See the primary
[ByteTrack reference](https://docs.ultralytics.com/reference/trackers/byte_tracker/)
and [tracker callbacks](https://docs.ultralytics.com/reference/trackers/track/).

Resolution: keep tracking enabled, as permitted by current integration contracts
and useful for supplied backend identity. Change only new_track_thresh to 0.50.
Module 02 startup rejects either high/new threshold above detector confidence
when tracking is enabled. Disabled tracking does not consume tracker YAML.
This is logical consistency, not experimentally optimal tuning. Track association
and confirmation can still legitimately affect which detections appear.

Files: configs/yolo_tracker.yaml; 02_yolo/config.py; inference/detector.py;
tests/test_tracking.py; tests/test_yolo_backend.py; README; integration owner notes.

Tests: default thresholds, high/new mismatch rejection, equal/lower new threshold
acceptance, actual initialization rejection before model loading, and disabled
tracking initialization despite unused inconsistent tracker settings.

## M02-R02 - MEDIUM - FIXED

Classification: MODULE 02 LOCAL FIX.

Evidence: existing fallback called model.to("cpu") for .pt or set predictor=None
for .onnx. Installed Ultralytics engine/model.py::_apply clears predictor when
model tensors are converted. Recreated trackers can restart integer IDs;
Module 03 stabilizer associates supplied identities by class_id + track_id.
A transparent rebuild could therefore preserve incorrect downstream continuity.

Resolution: any recognized accelerator inference failure with tracking enabled
latches a controlled failure. No model movement, CPU retry, predictor recreation
or valid detection packet occurs. YoloPipeline emits ERROR and empty detections.
Subsequent calls stay ERROR without invoking inference until an explicit reset.
Reset the enclosing processing chain, or use the existing upstream reset_required
signal so both detector and Module 03 histories reset. A local detector-only reset
while retaining downstream state is unsafe and explicitly documented. To switch
devices, restart the coordinated chain with CPU configuration.

CPU fallback at startup remains possible before any history exists. Untracked
runtime inference retains accelerator-to-CPU retry. No new status or reset signal
was introduced; Module 03 code is unchanged.

Files: inference/detector.py; tests/test_tracking.py; README; PIPELINE; DOD.

Tests: .pt/.onnx and cpu_fallback true/false tracked failures all produce ERROR,
keep predictor/device, perform no CPU movement, and block a later apparently
reused ID until explicit reset. Separate untracked .pt/.onnx tests preserve CPU
retry. Actual Module 03 integration verifies reset removes confirmation history.

## M02-R03 - MEDIUM - FIXED

Classification: SCHEMA/INTEGRATION DOCUMENTATION ALIGNMENT; owner review material
is prepared in [INTEGRATION_OWNER_NOTES.md](INTEGRATION_OWNER_NOTES.md).

Evidence: shared ObjectFrame reference_anchors is optional with an empty-list
default and no required-population rule. Active Module 02 leaves it empty.
INTEGRATION.md assigns calibration to Module 03; active OptimizationPipeline
uses a manual/ArUco coordinate_transformer and never reads that list. Old
classes.yaml/scaffold/Module 03 planning comments implied an anchor producer.

Decision: ReferenceAnchor/reference_anchors are reserved shared compatibility
leaves with no active semantic producer. Current Module 02 publishes [] even
for rack detections. Reference derivation/calibration belongs to Module 03,
published as ReferenceFrameInfo via SpatialFeaturePacket.reference_frame.
Empty legacy anchors do not mean reference loss.

Files: shared/schemas/object_frame.py (comments/docstring only);
perception/INTEGRATION.md; configs/classes.yaml (comments only);
03_optimization/PIPELINE.md and DEFINITION_OF_DONE.md (historical-plan notices);
Module 02 docs/deprecated scaffold notices and tests/test_object_frame.py.

Migration: none. Field names/types/defaults and serialized shape are unchanged.
Any future producer/consumer requires a new explicit integration decision, not
an inferred TODO implementation. No semantic rack calibration was added to YOLO.

Test: actual Module 03 manual calibration succeeds and publishes valid reference
information while both input/output legacy anchor lists remain empty.

## M02-R04 - MEDIUM - FIXED

Classification: MODULE 02 LOCAL FIX.

Evidence: opened test_tracking.py; all five tests were module-level skipped
NotImplementedError placeholders, with no implementation or fixture. Physical
crossing/lost/reacquired claims require footage and are not the active adapter API.
They were replaced with executable tests of the actual owned boundary.

Files: tests/test_tracking.py; tests/test_yolo_backend.py; README; DOD.

Coverage now executes: supplied ID persistence/change, None identity notices,
disabled tracking using predict and discarding IDs, healthy empty tracking frames
without fabricated lost objects, tracker/model lifecycle, default/invalid/equal
thresholds, disabled tracker validation, coordinated reset and accelerator fallback.

Module 02 now has **zero skipped tests**. Physical tracking quality remains an
explicit evaluation limitation; no mocked test claims to measure ByteTrack
crossing, loss/reacquisition or recognition accuracy.

## M02-R05 - LOW - FIXED

Classification: MODULE 02 LOCAL FIX.

Reproduction used real Module 01 preparation: source 745 x 480, max_width 640,
prepared shape 412 x 640; inverse scaling returned y2=480.00000000000006.
Resolution: clamp_source_box runs only AFTER source_detection. It corrects
excursions within four floating-point ULPs of the source bound and preserves
strictly positive area. Material excursions, nonfinite values or collapsed boxes
raise BackendOutputError and produce a controlled frame ERROR.

Files: inference/postprocess.py; pipeline.py; tests/test_coordinate_restore.py;
README; PIPELINE; DOD.

Tests: exact full-frame source bounds for the reviewer case, plus rejection of
a one-pixel overshoot, a materially negative coordinate and collapsed area.
No new scaling/preparation stage or upstream transform modification was added.

## M02-R06 - LOW - FIXED (ownership documentation)

Classification: INTEGRATION OWNER SIGN-OFF; script implementation unchanged.

Evidence: scripts/run_yolo.py is already committed in e33b21b. It correctly
delegates to the canonical yolo.cli and is referenced by README.
Both module and script --help commands run successfully from repository root.

Resolution: retain the working wrapper; document the historical integration
ownership exception and sign-off requirement in INTEGRATION_OWNER_NOTES.md.
No message to another owner, external sign-off or script rewrite is claimed.

Files: new INTEGRATION_OWNER_NOTES.md; README and this report only.
Verification: script remains absent from this repair's Git diff.

## M02-R07 - LOW - FIXED

Classification: MODULE 02 LOCAL FIX.

Evidence: runtime/reset failures previously logged only at DEBUG.
Resolution: one WARNING on entry into a failure episode, subsequent failures at
DEBUG, and INFO on the next successful inference. Structured packet diagnostics
continue every frame. Invalid upstream input does not falsely announce recovery.
This uses one instance-local Boolean under the existing pipeline lock, not a
new logging framework or per-frame warnings.

Files: pipeline.py; tests/test_yolo_stage.py; README; DOD.

Tests: repeated inference failures, recovery, a second failure episode and
repeated reset failure/recovery all assert exact warning/debug/recovery counts.

## M02-R08 - LOW - FIXED

Classification: MODULE 02 DOCUMENTATION FIX.

Evidence: repository-wide import/path searches found no active use of twenty
old scaffold leaves. AST inspection confirms all twenty contain only docstrings
and comments, with no executable definitions/imports. Package paths remain
retained; each now begins with DEPRECATED / UNUSED and explicitly marks the old
plan as historical. No file or compatibility path was blindly deleted.

All twenty are listed in the file inventory below. Module 01 remains responsible
for generic resize/color/equalization; Ultralytics for model-specific adaptation;
Module 03 for temporal confirmation and calibration.

Threshold documentation was also corrected: installed Ultralytics 8.4.165 NMS
uses strict confidence > threshold, while the project's post-filter uses >=.
Injected equality tests only establish the latter. NMS was not reimplemented.
See the [primary NMS reference](https://docs.ultralytics.com/reference/utils/nms/).

Dependency requirements intentionally remain unpinned per existing repository
policy. Installed version 8.4.165 is recorded as the version whose source was
inspected; native runtime verification on it remains blocked, not claimed passed.

## Tracking behavior after repair

| Item | Exact behavior |
|---|---|
| Repository YAML default | tracking=true; shared programmatic DetectorConfig default remains false |
| Detector confidence | 0.50 in configs/yolo.yaml |
| Tracker thresholds | track_high_thresh=0.50, new_track_thresh=0.50; both must be <= detector confidence when enabled |
| Tracked accelerator failure | ERROR/empty; no CPU retry/rebuild; inference paused until coordinated reset |
| Untracked accelerator failure | Existing permitted CPU retry and CPU_FALLBACK warning |
| Startup unavailable accelerator | Existing cpu_fallback policy can select CPU before histories exist |
| Reset | Existing upstream signal resets detector and Module 03; detector model retained where possible |
| Identity | Only supplied IDs; None valid; IDs can be reused after reset; no global physical identity, lost-object prediction or crossing-quality guarantee |

## Verification commands and actual results

Commands below were executed from repository root, in the required order:
narrow tests, actual integrations, full suite, then static/import/CLI checks.
Workspace-local basetemp avoids the known OS temporary-directory permission issue.

```powershell
.venv/Scripts/python.exe -m pytest 02_yolo/tests -q -p no:cacheprovider --tb=short --basetemp 02_yolo/.verification/minor-unit-final
.venv/Scripts/python.exe -m pytest 02_yolo/tests/test_yolo_backend.py::test_raw_backend_through_actual_module01_02_03 02_yolo/tests/test_yolo_stage.py::test_offline_actual_module03_consumer 02_yolo/tests/test_object_frame.py::test_stability_flag_after_confirmation 02_yolo/tests/test_object_frame.py::test_module03_calibrates_with_empty_legacy_anchors 02_yolo/tests/test_tracking.py::test_upstream_reset_clears_detector_and_optimizer_histories -q -p no:cacheprovider --tb=short --basetemp 02_yolo/.verification/minor-integration
.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider --tb=short --basetemp 02_yolo/.verification/minor-full
.venv/Scripts/python.exe -m yolo.tests.verify_types
.venv/Scripts/python.exe -m compileall -q 02_yolo yolo perception shared optimization 03_optimization integration
$module02RepairPython = @(git -c core.safecrlf=false diff --name-only -- '*.py')
.venv/Scripts/python.exe -m ruff check --extend-per-file-ignores '02_yolo/**/__init__.py:N999' $module02RepairPython
.venv/Scripts/python.exe -m ruff format --check $module02RepairPython
.venv/Scripts/python.exe -m yolo --help
.venv/Scripts/python.exe scripts/run_yolo.py --help
git -c core.safecrlf=false diff --check
python -m yolo.tests.verify_real_offline
```

| Check | Actual result |
|---|---|
| Baseline Module 02 rerun | 91 passed, 5 skipped |
| Final Module 02 suite | **117 passed, 0 skipped, 0 failed** |
| Actual Module 01/02/03 selected integrations | **5 passed** |
| Full repository suite | **271 passed, 99 skipped, 0 failed** |
| Ruff on all 30 touched Python files | All checks passed; 30 files already formatted |
| Mypy active owner source view | Success: no issues found in 10 source files |
| Syntax compilation | Passed |
| Canonical/legacy import assertions | Passed, detector aliases identical |
| Module/script CLI --help | Both passed from repository root |
| Git whitespace check | Passed |
| Native offline smoke attempted | Failed before inference: WinError 4551 loading torch.dll |

The 99 full-suite skips are existing non-Module-02 scaffolds. No network, GPU,
camera or real model is needed by Module 02 unit/integration tests; their existing
socket-rejection fixture remains enabled.

Ruff's N999 exception preserves the established numbered package directory.
Initial lint/format checks exposed that naming warning and mixed line endings
in newly annotated scaffolds; only touched Python files were normalized and the
final checks passed. No algorithm was reformatted in an unrelated module.

Mypy checks exact unchanged copies of the ten active owner sources under a valid
temporary package name, since it does not follow the dynamic yolo.__path__ locator.
No third-party internals or inactive scaffolds are claimed as type coverage.

## Files changed / created

Paths are repository-relative. Every file in this repair diff is listed.

| File | Why changed |
|---|---|
| 02_yolo/config.py | Validate enabled tracker threshold relationship |
| 02_yolo/inference/detector.py | Enforce thresholds; latch tracked accelerator failures; prevent CPU rebuild/reused IDs |
| 02_yolo/inference/postprocess.py | Source-space numerical boundary correction helper |
| 02_yolo/pipeline.py | Apply correction after existing restoration; failure/recovery transition logs |
| 02_yolo/tests/test_tracking.py | Replace five nonexecutable placeholders with active owned-boundary tracking regressions |
| 02_yolo/tests/test_yolo_backend.py | Startup threshold mismatch/disabled tracking regression |
| 02_yolo/tests/test_coordinate_restore.py | Reviewer boundary reproduction and material-error rejection |
| 02_yolo/tests/test_object_frame.py | Actual Module 03 calibration with empty legacy anchors |
| 02_yolo/tests/test_yolo_stage.py | Failure/reset logging episode regressions |
| 02_yolo/README.md | Exact thresholds, fallback/reset, roundoff, anchors, logging, version/test limits |
| 02_yolo/PIPELINE.md | Numerical correction and safe tracked failure behavior; no boundary change |
| 02_yolo/DEFINITION_OF_DONE.md | Minor-repair acceptance and zero skipped unit coverage |
| 02_yolo/REPAIR_REPORT.md | Current evidence per finding, commands, inventory and review readiness |
| configs/yolo_tracker.yaml | Only functional cross-owner config change: new-track threshold 0.60 -> 0.50 |
| configs/classes.yaml | Comments clarify reference roles are not Module 02 anchor output; IDs unchanged |
| shared/schemas/object_frame.py | Comments/docstring clarify reserved reference field; packet API unchanged |
| perception/INTEGRATION.md | Explicit legacy-anchor/calibration ownership |
| 03_optimization/PIPELINE.md | Notice that old anchor-derived plan is historical; no Module 03 code change |
| 03_optimization/DEFINITION_OF_DONE.md | Same historical-plan ownership notice |
| 02_yolo/INTEGRATION_OWNER_NOTES.md (new) | Config/schema wording review and existing script ownership sign-off material |

The following twenty files each receive only the same deprecation/ownership
notice and line-ending normalization; historical contents/import paths remain:

- 02_yolo/preprocessing/__init__.py
- 02_yolo/preprocessing/coordinate_restore.py
- 02_yolo/preprocessing/letterbox.py
- 02_yolo/preprocessing/normalize.py
- 02_yolo/detection/__init__.py
- 02_yolo/detection/bbox_validator.py
- 02_yolo/detection/detection_filter.py
- 02_yolo/detection/object_state.py
- 02_yolo/tracking/__init__.py
- 02_yolo/tracking/object_tracker.py
- 02_yolo/tracking/track_manager.py
- 02_yolo/tracking/track_state.py
- 02_yolo/stability/__init__.py
- 02_yolo/stability/detection_stability.py
- 02_yolo/reference/__init__.py
- 02_yolo/reference/anchor_extractor.py
- 02_yolo/output/__init__.py
- 02_yolo/output/object_frame_builder.py
- 02_yolo/inference/yolo_loader.py
- 02_yolo/inference/yolo_inference.py


No scripts/run_yolo.py, Module 01 processing code, Module 03 processing code,
requirements files, experiment weights or class IDs were changed.

## Remaining limitations and final readiness

- Actual experiment weights and final classes.yaml IDs have not been supplied.
- **Native inference not verified in this environment.** The attempted smoke
  cannot load installed PyTorch torch.dll because Windows Application Control
  returns WinError 4551. This repair did not weaken Windows policy or bypass it.
- Native CPU/GPU/ONNX/MPS execution and native-code network isolation are unverified.
- Detection accuracy, physical tracker crossing/reacquisition quality, FPS and
  target-device latency have not been measured. Model-free tests are contract
  evidence, not experimental validation.
- Config/schema wording and the historical script exception are prepared for
  integration-owner sign-off; no external approval is fabricated.
- Module 03 must consume original-pixel boxes, allow None IDs/empty scenes and
  clear its histories during coordinated resets. Never reset only a detector
  while retaining temporal state when IDs can be reused.

**READY FOR CLAUDE OPUS 5.5 HIGH FINAL REVIEW.**
Reason: all evidence-backed findings are repaired/documented, all owned tests and
full regression checks pass, the authoritative boundary is preserved, and external
asset/native/benchmark limits are explicit.
