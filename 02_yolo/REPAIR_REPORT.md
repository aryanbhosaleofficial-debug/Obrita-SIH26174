# Module 02 repair report - 2026-10-04

## Module 02 status

**COMPLETE** for the implemented software boundary and model-free integration.
**Native deployment verification remains blocked** by Windows Application Control
rejecting torch.dll (WinError 4551). Real trained detection, physical GPU execution
and an actual disconnected-camera demonstration are not claimed complete.
The required local trained model and final class IDs must be supplied by the team.

The tree already contained staged/unstaged Module 02 implementation changes at
inspection. They were reviewed, preserved and extended; the inventories below
describe the complete deliverable relative to HEAD, not exclusive authorship.
No commit, dependency installation or large model addition was performed.

## Architecture confirmed

```text
External FramePacket
 -> Module 01 perception.core.FrameProcessor.process
 -> shared.schemas.PreparedFrame
 -> Module 02 yolo.pipeline.YoloPipeline.process
    -> prepared image/scale checks
    -> local Ultralytics predict / configured optional backend track
    -> parse_results -> canonical Detection in prepared pixels
    -> confidence/class filter + box validation/diagnostic clipping
    -> PreparedFrame.source_detection (exactly once)
 -> shared.schemas.ObjectFrame (original-source pixels)
 -> Module 03 optimization.pipeline.OptimizationPipeline.process(prepared, objects)
 -> shared.schemas.OptimizationOutputPacket
```

The newer perception/INTEGRATION.md decision overrides obsolete numbered scaffold
plans. Module 01 and all shared schemas were retained unchanged. Module 03's
existing implementation is exercised without replacing its algorithms. Its
separate input/input_validator.py remains a teammate scaffold; integration tests
target its active OptimizationPipeline consumer and metadata checks instead.

## Files changed

Paths below are relative to the repository root. Every modified tracked file in
this deliverable is listed; unrelated modules are unchanged.

| File | Change and reason |
|---|---|
| 02_yolo/__init__.py | Correct ownership description: PreparedFrame input, local detection, Module 03 stability/calibration |
| 02_yolo/pipeline.py | Snapshot configuration, validate inference prerequisites, serialized lifecycle, once-only initialization, diagnostic runtime/reset recovery, canonical metadata/coordinate conversion, no partial failed output; drain backend warnings on failed frames to avoid contaminating recovery |
| 02_yolo/inference/detector.py | Local backend lifecycle, strict config/device/tracker startup, offline import checks, CPU retry, parser isolation, validated clipping and Python-float geometry; selected device also passed into exported-model metadata setup |
| 02_yolo/inference/postprocess.py | Real external Results conversion with finite scores/IDs, deterministic mapping, batch/array/shape validation; avoids undoing library letterbox twice |
| 02_yolo/inference/class_map.py | Validate model class-map shape, IDs/names and exact agreement with local project mapping |
| 02_yolo/tests/test_coordinate_restore.py | Replace inactive cases with actual prepared-to-source restoration, edge, portrait/landscape framework coordinates and rounded-scale tests |
| 02_yolo/tests/test_detection.py | Activate confidence/class/box/empty/missing-weight regressions |
| 02_yolo/tests/test_object_frame.py | Activate contract/metadata/original-coordinate checks; prove confirmation belongs to Module 03 |
| 02_yolo/tests/test_tracking.py | Explain five retained skipped footage-evaluation cases; avoid claiming untested physical identity/lifecycle quality |
| 02_yolo/README.md | Document actual architecture, contracts, installation, local assets, config/devices/classes, coordinates, lifecycle, errors, CLI/testing and verification limits |
| 02_yolo/PIPELINE.md | Replace obsolete competing preprocessing/stability plan with active owner path |
| 02_yolo/DEFINITION_OF_DONE.md | Align acceptance with authoritative contracts; separate implemented behavior from unresolved deployment/evaluation gates |
| 02_yolo/models/README.md | Fix actual detector.model_path key and YAML-relative path behavior; explain absent weights/classes and supported local formats |
| scripts/run_yolo.py | Existing convenience launcher delegates to the canonical Module 02 CLI rather than a scaffold path |

## Files added

| File | Purpose |
|---|---|
| 02_yolo/.gitignore | Ignore local verification assets/caches without changing global repository ignore policy |
| 02_yolo/__main__.py | python -m yolo delegates to the same smoke CLI |
| 02_yolo/cli.py | Local single-image Module 01 -> Module 02 smoke, JSON output and defined exit codes |
| 02_yolo/config.py | Strict detector-only YAML loading, shared DetectorConfig validation/snapshot, path/device normalization and local tracker validation |
| 02_yolo/input_validation.py | Validate prepared image and reversible scale prerequisites; no frame preparation or ordering policy |
| 02_yolo/tests/conftest.py | Network-rejecting synthetic backend/raw-result fixtures and actual upstream frame preparation |
| 02_yolo/tests/test_yolo_backend.py | Mock framework startup/device/offline/lifecycle failures, adapter conversion and complete actual 01/02/03 contract path |
| 02_yolo/tests/test_yolo_cli.py | Canonical CLI JSON/metadata behavior, missing/undecodable input and missing local weights |
| 02_yolo/tests/test_yolo_stage.py | Stage/parser/config/recovery/concurrency/legacy/import and downstream integration regressions |
| 02_yolo/tests/verify_real_offline.py | Opt-in fresh-process CPU/tracker/CLI smoke with temporary random weights and Python network audit; no recognition benchmark |
| 02_yolo/tests/verify_types.py | Reproducible mypy check of unchanged copies of ten active sources under a valid temporary package name |
| 02_yolo/REPAIR_REPORT.md | This implementation, verification and limitation record |

The temporary repository-wide search output was removed. Test assets are ignored;
none are a trained model or required production resource.

## Contracts used / inspection answers

| Question | Confirmed answer |
|---|---|
| PreparedFrame definition/output | shared/schemas/prepared_frame.py: image, scale_x/scale_y, retained source, status/diagnostics/timing, accepted/missing/reset information |
| ObjectFrame definition/output | shared/schemas/object_frame.py: frame_id, timestamp_s, image_width/image_height, detections, source_id/session_id, status/diagnostics/timing and optional anchors |
| Detection definition | shared/schemas/observations.py, using its BoundingBox; object_frame.DetectedObject is the same class alias |
| Published coordinates | Original FramePacket pixels, never model/prepared/normalized coordinates |
| Upstream preparation | perception/core.py and preprocessing.py validate and prepare BGR; optional max_width resize/equalization; no crop, letterbox or rotation |
| Model-specific preparation | Ultralytics internally adapts tensors, resizes/letterboxes and performs NMS; its Results.xyxy are already in the prepared input image space |
| Remaining transform | Call authoritative PreparedFrame.source_detection using actual independent x/y scales once; rounding is tested |
| Metadata | Preserve source frame_id, timestamp_s, source_id/session_id and original width/height; no timestamp generation. ObjectFrame has no free-form orientation field; source metadata stays with PreparedFrame |
| Module 03 input | OptimizationPipeline.process(prepared, objects) with matching six metadata fields, original-pixel canonical detections, valid empty lists and shared status semantics |
| Legacy import | perception/detector.py re-exports yolo.inference.detector; no extra implementation required |
| Model/config locality | DetectorConfig and configs/yolo.yaml, resolved existing local .pt/.onnx path plus required exact classes.yaml; missing assets fail before loading |
| Offline readiness | No module network/client code; runtime auto-install disabled and offline import state checked. Network-rejecting model-free tests passed; native audit could not reach inference on this machine |
| Model-free tests | Inject ObjectDetector or raw mocked Ultralytics outputs; no GPU, camera, real weights or internet needed |
| Ownership conflicts | Only obsolete scaffold docs assigned competing preparation/confirmation/calibration here; replaced active documentation. Inactive scaffold leaves remain unused, not a second pipeline |

See the linked primary Ultralytics result/offline references in README.md.

## YOLO backend / design decisions

- Backend remains Ultralytics; no replacement detector or duplicate packet classes.
- YOLO(existing_absolute_path, task="detect") loads once; predict/optional track
  reuse that instance. Startup failures clear cached model/class state and raise
  InitializationError. Local paths are validated before the framework is invoked.
- Configuration stays in shared.config.DetectorConfig; no shared API changes or
  second image-size setting. Framework-specific input sizing uses its default.
  YAML paths resolve relative to their file; constructor/CLI paths to the CWD.
- Auto selects available CUDA 0, otherwise CPU. Explicit CPU works; CUDA aliases
  and device counts are validated. Optional existing MPS remains supported.
  cpu_fallback controls unavailable accelerator/inference retry behavior; warnings
  remain attached to the affected frame.
- YOLO_OFFLINE=true and YOLO_AUTOINSTALL=false are set before framework import.
  Conflicting flags, enabled auto-install and an already-online import fail startup.
  No process-global framework monkey-patching or native network-policy bypass is used.
- Class names exactly match the configured local model map. IDs are never rounded
  or fabricated. Tracking is optional and explicitly authorized by current contracts;
  only supplied IDs are published. Local tracker YAML is validated and ReID disabled.
- Preserve row order. Reject invalid scores/IDs/boxes; partially outside boxes are
  clipped with diagnostics, completely outside or collapsed boxes are rejected.
  Structural corruption/inference failure emits ERROR with no partial observations.
- Model/stream lifecycle uses locks; no asynchronous framework or camera ownership.
  Module 01 governs frame ordering and reset signals; Module 03 governs continuity,
  temporal votes, calibration and interactions. Backend IDs are not permanent identity.
- Capability notices do not lower healthy status. Empty output is NO_DETECTION.
  Startup errors propagate; per-frame exceptions are observable and may recover.
  Detection timing is measured, with initialization excluded; FPS is not invented.

## Tests added/repaired

The active tests below use real stage implementations and synthetic backend data.
Parameterization expands them into 91 passing cases. The network fixture rejects
connect, sendto and getaddrinfo. Each test's name identifies its assertion subject;
the inventory following verification gives the complete function list by file.

Key end-to-end checks:

- test_raw_backend_through_actual_module01_02_03: mocked external result passes
  through actual upstream RGB/rounded resize, parser, filter/restoration and actual
  optimizer; all correlation metadata and healthy empty consumption asserted.
- test_offline_actual_module03_consumer: canonical restored geometry and explicit
  Module 03 coordinate fallback accepted with networking prohibited.
- test_stability_flag_after_confirmation: Module 02 never confirms detections;
  only the actual Module 03 stage establishes stability over consecutive frames.
- test_failed_frame_drains_backend_warnings: failed CPU retry reports its warning
  once; next healthy frame recovers without stale degradation.
- test_preimported_online_backend_rejected / test_autoinstall_enabled_rejected:
  runtime policy fails before model loading even when environment strings look safe.

Five historical tracker footage cases are skipped, not counted as passing coverage.
The remaining 99 full-suite skips are existing non-Module-02 scaffolds.

## Verification commands / actual results

Commands were run from the repository root unless noted. Workspace-local basetemp
was used after the OS temporary directory became inaccessible following the
permission-profile change. The directory 02_yolo/.verification was created first.

```powershell
.venv/Scripts/python.exe -m pytest 02_yolo/tests -q -p no:cacheprovider --tb=short --basetemp 02_yolo/.verification/unit-tmp
.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider --tb=short --basetemp 02_yolo/.verification/full-tmp
.venv/Scripts/python.exe -m pytest 02_yolo/tests/test_yolo_backend.py::test_raw_backend_through_actual_module01_02_03 02_yolo/tests/test_yolo_stage.py::test_offline_actual_module03_consumer 02_yolo/tests/test_object_frame.py::test_stability_flag_after_confirmation -q -p no:cacheprovider --basetemp 02_yolo/.verification/integration-tmp
.venv/Scripts/python.exe -m compileall -q 02_yolo yolo perception shared optimization 03_optimization integration scripts/run_yolo.py
.venv/Scripts/python.exe -m yolo.tests.verify_types
.venv/Scripts/python.exe -m yolo --help
.venv/Scripts/python.exe scripts/run_yolo.py --help
git -c core.safecrlf=false diff HEAD --check
python -m yolo.tests.verify_real_offline
```

| Verification | Real result |
|---|---|
| Module 02 pytest | 91 passed, 5 skipped; no failures/errors |
| Full repository pytest | 245 passed, 104 skipped; no failures/errors |
| Selected actual 01/02/03 integrations | 3 passed |
| Canonical/legacy import assertions | Passed, aliases are identical |
| Syntax compilation | Passed |
| Active owner mypy via verify_types | Success, no issues in 10 source files |
| Ruff lint / formatting checks | All checks passed; 20 files already formatted |
| Module/script CLI help | Both exited successfully |
| Git whitespace check | Passed |
| Opt-in real CPU/offline smoke | Failed before inference: Windows Application Control WinError 4551 loading torch.dll |

Lint and formatting used this exact target list (existing numbered directory
requires the documented naming exception):

```powershell
.venv/Scripts/python.exe -m ruff check --per-file-ignores '02_yolo/__init__.py:N999' 02_yolo/__init__.py 02_yolo/__main__.py 02_yolo/cli.py 02_yolo/config.py 02_yolo/input_validation.py 02_yolo/pipeline.py 02_yolo/inference/detector.py 02_yolo/inference/postprocess.py 02_yolo/inference/class_map.py 02_yolo/tests scripts/run_yolo.py
.venv/Scripts/python.exe -m ruff format --check 02_yolo/__init__.py 02_yolo/__main__.py 02_yolo/cli.py 02_yolo/config.py 02_yolo/input_validation.py 02_yolo/pipeline.py 02_yolo/inference/detector.py 02_yolo/inference/postprocess.py 02_yolo/inference/class_map.py 02_yolo/tests scripts/run_yolo.py
```

Mypy's dynamic-package lookup initially checked only the yolo facade or could not
locate subpackages. Those attempts are not claimed as owner coverage: verify_types
checks exact unchanged active source copies under a valid temporary yolo package
with that package first on MYPYPATH. Shared/third-party dependencies are followed
silently; inactive scaffold leaves and external internals are outside that check.

Initial baseline before final repairs: Module 02 80 passed/5 skipped; full repository
234 passed/104 skipped. Temporary-directory failures were environmental setup errors
and resolved by using a fresh workspace basetemp. The native smoke was attempted
again after unrestricted permissions but remained blocked by Windows policy;
no successful native execution or zero-network-attempt inference result is claimed.

## Remaining limitations

- Local experiment-trained YOLO weights and final class IDs are absent. The real
  default configuration deliberately fails setup until they are supplied.
- Windows Application Control prevents the installed Python 3.14 PyTorch DLL from
  loading. The project Python 3.11 test environment has no real YOLO/PyTorch backend;
  unit tests need neither. Use an approved compatible demo environment for native
  inference verification; this repair did not alter Windows security policy.
- CPU/CUDA/MPS selection and ONNX metadata device plumbing are mocked tests;
  physical accelerator, exported ONNX and MPS inference are unverified.
- Recognition accuracy, real-scene tracking quality, FPS and target-device latency:
  **not measured**. Random blank-frame smoke would not establish them even if run.
- Five historical labelled-footage tracker scenarios remain skipped. Track quality,
  lost/reacquired semantics, anchors and temporal confirmation are not fabricated.
- Inactive historical planning leaves remain to avoid unrelated restructuring.
  Their TODOs are not the current public API. Source-tree package locators need
  separate packaging work for deployment outside the documented repository layout.
- Network-rejecting model-free tests cover Python socket APIs, not native-code
  networking or all third-party versions. Rerun native offline audit on the demo
  environment, then the actual disconnected trained-model demonstration.

## Module 03 integration risks / review readiness

Module 03 must consume original-source-pixel canonical detections with matching
frame/time/source/session/dimensions and retain the same PreparedFrame. None IDs
and empty detections are valid. Check ERROR/INVALID_INPUT before object-dependent
processing. The normal chain's invalid upstream frames are handled by the actual
optimizer; a caller supplying a corrupted PreparedFrame directly must gate the
Module 02 status (the optimizer's separate receiving-validator file is a scaffold).

Do not treat backend IDs as permanent identity or default Detection stability,
track quality/age, reference anchors or motion fields as measured evidence.
Module 03 owns those temporal/reference meanings. Reset the enclosing chain for
source/session changes; backend resets can reuse integers. No shared schema or
consumer API changes were needed. Existing Module 01 historical reports were not
overwritten or reused as verification of this repair.

**Ready for independent implementation/contract review: YES.**
**Ready for a verified trained offline camera demonstration: NOT YET**, pending
local assets, an environment that permits native inference and real-scene evaluation.

## Complete active test function inventory

### tests/test_coordinate_restore.py

| Test | Verifies |
|---|---|
| `test_no_padding` | No padding |
| `test_horizontal_letterbox_padding` | Horizontal letterbox padding |
| `test_vertical_letterbox_padding` | Vertical letterbox padding |
| `test_bbox_touching_image_edge` | Bbox touching image edge |
| `test_invalid_bbox` | Invalid bbox |
| `test_letterbox_restore_round_trip` | Letterbox restore round trip |

### tests/test_detection.py

| Test | Verifies |
|---|---|
| `test_confidence_threshold_filtering` | Confidence threshold filtering |
| `test_disallowed_classes_removed` | Disallowed classes removed |
| `test_invalid_boxes_rejected` | Invalid boxes rejected |
| `test_empty_detections_valid_object_frame` | Empty detections valid object frame |
| `test_missing_model_file_clear_error` | Missing model file clear error |

### tests/test_object_frame.py

| Test | Verifies |
|---|---|
| `test_frame_metadata_copied_unchanged` | Frame metadata copied unchanged |
| `test_coordinates_in_original_frame` | Coordinates in original frame |
| `test_uses_shared_schema` | Uses shared schema |
| `test_missing_anchor_reported` | Missing anchor reported |
| `test_stability_flag_after_confirmation` | Stability flag after confirmation |

### tests/test_yolo_backend.py

| Test | Verifies |
|---|---|
| `test_device_policy` | Device policy |
| `test_mps_existing_optional_backend` | Mps existing optional backend |
| `test_unavailable_or_invalid_cuda_fails_at_startup` | Unavailable or invalid cuda fails at startup |
| `test_model_reuse_across_resolution_reset` | Model reuse across resolution reset |
| `test_real_adapter_to_module_contract_and_filtering` | Real adapter to module contract and filtering |
| `test_model_class_mismatch_never_leaves_initialized_cache` | Model class mismatch never leaves initialized cache |
| `test_backend_missing_is_actionable` | Backend missing is actionable |
| `test_unreadable_or_invalid_model_reports_loader_failure` | Unreadable or invalid model reports loader failure |
| `test_configured_tracker_uses_only_local_yaml` | Configured tracker uses only local yaml |
| `test_offline_flag_conflict_does_not_import_or_load` | Offline flag conflict does not import or load |
| `test_local_tracking_bad_yaml_and_missing_parameters` | Local tracking bad yaml and missing parameters |
| `test_unsupported_model_format_fails_without_backend` | Unsupported model format fails without backend |
| `test_preimported_online_backend_rejected` | Preimported online backend rejected |
| `test_autoinstall_enabled_rejected` | Autoinstall enabled rejected |
| `test_exported_backend_metadata_uses_selected_device` | Exported backend metadata uses selected device |
| `test_raw_backend_through_actual_module01_02_03` | Raw backend through actual module01 02 03 |

### tests/test_yolo_cli.py

| Test | Verifies |
|---|---|
| `test_cli_json_uses_actual_upstream_and_stage` | Cli json uses actual upstream and stage |
| `test_cli_rejects_missing_or_undecodable_image` | Cli rejects missing or undecodable image |
| `test_cli_missing_local_weights_is_setup_error` | Cli missing local weights is setup error |

### tests/test_yolo_stage.py

| Test | Verifies |
|---|---|
| `test_one_object_metadata_source_coordinates_and_no_mutation` | One object metadata source coordinates and no mutation |
| `test_empty_and_multiobject_order_filtering` | Empty and multiobject order filtering |
| `test_malformed_prepared_image_does_not_initialize` | Malformed prepared image does not initialize |
| `test_invalid_restoration_scale_rejected_before_inference` | Invalid restoration scale rejected before inference |
| `test_missing_source_is_programming_error` | Missing source is programming error |
| `test_upstream_error_and_degradation_propagate` | Upstream error and degradation propagate |
| `test_invalid_individual_rows_clipping_and_duplicates` | Invalid individual rows clipping and duplicates |
| `test_failure_after_conversion_never_leaks_partial_results` | Failure after conversion never leaks partial results |
| `test_startup_error_propagates_and_frame_failure_recovers` | Startup error propagates and frame failure recovers |
| `test_threads_serialize_and_initialize_once` | Threads serialize and initialize once |
| `test_parser_preserves_order_tracks_and_no_double_letterbox` | Parser preserves order tracks and no double letterbox |
| `test_parser_never_fabricates_integer_identity` | Parser never fabricates integer identity |
| `test_structural_result_corruption_is_explicit` | Structural result corruption is explicit |
| `test_standalone_yaml_relative_paths_and_snapshot` | Standalone yaml relative paths and snapshot |
| `test_bad_standalone_config_rejected` | Bad standalone config rejected |
| `test_no_implicit_mock_production_path` | No implicit mock production path |
| `test_legacy_import_is_canonical` | Legacy import is canonical |
| `test_temporary_tracker_reset_failure_is_explicit` | Temporary tracker reset failure is explicit |
| `test_offline_actual_module03_consumer` | Offline actual module03 consumer |
| `test_failed_frame_drains_backend_warnings` | Failed frame drains backend warnings |
| `test_empty_external_boxes` | Empty external boxes |
| `test_invalid_external_confidence_is_discarded` | Invalid external confidence is discarded |
| `test_clipped_numpy_geometry_serializes` | Clipped numpy geometry serializes |
