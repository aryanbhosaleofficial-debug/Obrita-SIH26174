# Modules 01–05 repair and verification

Branch: `v1`, based on `77295e9`. Work is left uncommitted for review.
The pre-existing untracked `global_pytest.log` was preserved.

## Result

The baseline five-module chain executes offline with genuine module processing.
Module 05 has configurable deterministic rules, confidence aggregation, unknown
handling, conflict reporting, frame-keyed temporal confirmation and one emission
per continuous action. Module 04 production code was not changed.

```text
External source -> shared FramePacket
01 perception.core.FrameProcessor -> shared PreparedFrame (source retained)
02 yolo.pipeline.YoloPipeline -> shared ObjectFrame
03 optimization.pipeline.OptimizationPipeline(PreparedFrame, ObjectFrame)
   -> shared OptimizationOutputPacket
      (SpatialFeaturePacket + current objects/interactions + temporal snapshots)
04 boundary.boundary_pipeline.BoundaryPipeline.process_optimization(packet, FramePacket)
   -> shared BoundaryOutputPacket
05 fusion.pipeline.FusionPipeline.process(OptimizationOutputPacket, BoundaryOutputPacket)
   -> shared ActivityEvent
```

`integration.chain.PerceptionChain` remains authoritative for 01–03.
`integration.milestone.MilestonePipeline` extends that chain through 04–05.
`scripts/run_fusion.py` is a thin launcher for `integration.cli.main`;
`run_camera.py` delegates to the same capture/preparation support.

## Architecture classification

The per-file [architecture inventory](MODULES_01_05_ARCHITECTURE.csv) classifies
362 Python files across the numbered modules, compatibility packages, shared
contracts, scripts and tests as AUTHORITATIVE IMPLEMENTATION, COMPATIBILITY
WRAPPER, LEGACY, TEST or SCAFFOLD. An inactive scaffold is not an alternative
implementation. Directory-only package initializers are compatibility/export
boundaries. Configuration YAML files are runtime authorities.

| Area | Authority / classification |
| --- | --- |
| Module 01 | `perception/core.py`, `preprocessing.py`: AUTHORITATIVE IMPLEMENTATION; historical `01_perception_core/` planning leaves: SCAFFOLD |
| Module 02 | `02_yolo/core/`, SIH adapters, config, pipeline, detector/parser, input source and class mapping: AUTHORITATIVE IMPLEMENTATION; deprecated planning leaves: SCAFFOLD |
| Module 03 | `pipeline.py`, `optimizer.py`, hand/pose tracker interfaces, coordinate transforms, stabilizer/association and packet builder: AUTHORITATIVE IMPLEMENTATION; unused historical ROI/landmark/gesture leaves as inventoried |
| Module 04 | Existing boundary pipeline, validated config, target selection, segmentation, contour/features, temporal classifier and packet builder: AUTHORITATIVE IMPLEMENTATION; unchanged |
| Module 05 | `pipeline.py`, strict config and all input/evidence/fusion/temporal/HAR leaves: AUTHORITATIVE IMPLEMENTATION |
| Import-safe packages | `yolo/`, `optimization/`, `boundary/`, `fusion/`, `pose_tracking/`: COMPATIBILITY WRAPPER; no copied algorithms |
| `perception/` aliases | Compatibility exports delegate to owner code; core/preprocessing remain authoritative |
| `har/` | No root package exists or is required; Module 05 uses `fusion.har` |
| Existing procedure demo | `run_full_pipeline.py` and `main.py` remain a separate scripted-event FSM demonstration; not the perception runner |

## Commands and observed verification

All commands ran from the repository root with the installed Python environment.
No setup install, model download or model fabrication was performed.

| Command | Result |
| --- | --- |
| `python -m compileall .` | PASS, exit 0 |
| `python -m pytest -q` (also `--tb=short -ra --junitxml=tests_tmp/milestone-tests.xml`) | 885 passed, 47 skipped, 0 failed, 0 errors |
| `python -m pytest --collect-only -q` | 931 test items collected; one additional collection-time model skip |
| `python -m pytest -q 05_perception_fusion/tests` | 46 passed |
| Module 04 independent and receiving-path regression run | 194 passed, 5 existing feature skips |
| `python scripts/run_yolo.py -h` | PASS |
| `python scripts/run_optimization.py --synthetic --output tests_tmp/optimization-final.jsonl` | PASS |
| `python scripts/run_boundary.py --synthetic --frames 10` | PASS; confirmed stationary boundary output |
| `python scripts/run_fusion.py --synthetic` | PASS; 36 frames, 2 events, 0 invalid frames |
| `python scripts/run_camera.py --synthetic --max-frames 5` | PASS |
| `python scripts/run_camera.py --video test_video.mp4 --max-frames 2` | PASS; actual local video decode + Module 01 processing |
| Real runner with all three absent model paths enabled | Clean actionable startup failure before camera/inference imports |

The final synthetic event file contains `touch_object` at frame 4 and
`move_object` at frame 17. Final empty frames produce `unknown`. Detector and hand
inference initialization counters are tested to equal one for the sequence.
Camera/video cleanup, Ctrl+C cleanup, source preservation, backend failure
diagnostics, event deduplication and logging are tested.

The 47 skips are 38 historical inactive planning-interface tests, five existing
optional/unsupported Module 04 feature tests, three explicit real-model gates,
and one collection-time missing MediaPipe-model skip. They are not silently
passing inference tests. The final test log and JUnit report are under ignored
`tests_tmp/`; no runtime output is intended for source control.

A synthetic run measured a median pipeline time around 2.4 ms and fusion around
0.07 ms in this environment. These are fixture-processing measurements, not a
real model benchmark, target-hardware guarantee, activity accuracy evaluation
or real-world latency claim. Per-frame timings are available in runner diagnostics.

## Root causes and targeted repairs

Initial `python -m pytest --tb=short` collected successfully. Its failures were
Windows temporary-directory access errors, not package collection errors. The
same suite using a writable local temp directory passed 817 tests before repair.
`pytest.ini` now selects importlib collection and an ignored repository-local
fixture path; root `conftest.py` creates its parent for fresh checkouts.
Temporary copied source is excluded from recursive collection.

The existing root locators for yolo/optimization/boundary were reliable and
preserved. Stable locators were added for new fusion and optional pose imports;
tests and CLI execution need no VS Code PYTHONPATH or test-order bootstrap.
New direct scripts share one launcher bootstrap, instead of production modules
injecting sys.path.

The SIH YOLO wrapper inherited a default-enabled localhost Qwen worker from its
standalone detector core. The SIH default is now disabled. Separate standalone
semantic/voice demonstrations were preserved; their tests enable semantic
behavior explicitly when exercising it.

## Offline and rack-relative evidence

The network audit found an existing urllib-based localhost verifier in Module
02's separate semantic extension. The milestone does not activate it; a
network-denying integration test runs all five stages and confirms the worker is
disabled. Existing detector tests cover missing local files, disabled
Ultralytics auto-install/online flags, class-map validation and local tracker
ReID restrictions. MediaPipe adapters load existing local Tasks paths only.
There is no cloud HAR or model downloading in the milestone.

The manual/ArUco Module 03 transform creates reference polygons and hand/pose
reference landmarks. Stabilization computes rack-relative object velocity and
stores it on current ObjectFrame detections inside OptimizationOutputPacket.
Module 04 receives the same reference metadata; Module 05 consumes that actual
velocity to confirm `move_object`. Tests assert creation, storage, propagation
and consumption, and reject uncalibrated image-space motion as rack motion.
Existing coordinate tests cover transforms and physical reference rotations.
This is the hackathon approximation, not proof of microgravity operation.

## Real inference and deployment assets

The audit inspected the checkout including ignored files (excluding generated
test fixtures) and the existing local repository ZIP. No production weights or
Tasks models were present; the ZIP contains none. Historical manifests and
verification documents do not imply installation in this checkout.

| Inference | Actual default local path | Current result |
| --- | --- | --- |
| YOLO | `02_yolo/models/experiment_objects.pt` via `configs/yolo.yaml` | NOT VERIFIED — missing model |
| Hand | `models/hand_landmarker.task` via `configs/optimization.yaml` | NOT VERIFIED — missing model |
| Optional pose helper | `06_pose_tracking/models/pose_landmarker_lite.task` via existing helper YAML | NOT VERIFIED — missing model; disabled by default |

Also supply a complete class ID/name taxonomy exactly matching your YOLO
checkpoint. `configs/classes.yaml` intentionally retains unset IDs because that
taxonomy was not supplied. Pass a real mapping with `--classes` or complete the
project mapping from genuine checkpoint metadata. Do not invent weights/IDs.
Optional local inference libraries must be installed before deployment, using
a supported Python environment and `requirements-perception-inference.txt`.

```bash
python scripts/run_fusion.py --video path/to/demo.mp4 \
  --model path/to/genuine-weights.pt --classes path/to/matching-classes.yaml \
  --hand-model path/to/hand_landmarker.task
# Add --pose-model path/to/pose_landmarker_lite.task to enable the body helper.
```

CLI asset paths override owner YAML paths; YAML paths resolve relative to their
owner file. Assets remain Git-ignored. Startup checks report all missing enabled
models concisely, before opening the camera. Model-free tests inject inference
backends; no real model inference or real-scene accuracy was claimed.

## Module status and freeze recommendation

| Module | Independent | Integrated | Verification | Freeze recommendation |
| --- | --- | --- | --- | --- |
| 01 | PASS: preparation, local video and synthetic capture | PASS | Source/contract tests | FREEZE |
| 02 | PASS: non-inference code | PASS with inference fake | Filtering, restoration, config, offline guards | DO NOT FREEZE deployment until genuine weights/classes are verified |
| 03 | PASS: standalone synthetic and helper adapter | PASS with inference fakes | Stabilization, associations, rack flow and contracts | DO NOT FREEZE deployment until the enabled hand model is verified |
| 04 | PASS for existing supported baseline | PASS | Original behavior preserved, no production file changes | FREEZE supported baseline |
| 05 | PASS: deterministic rule baseline | PASS | 46 unit tests plus actual upstream integration | FREEZE baseline code |

Remaining deployment blockers: the listed required local weights/hand model and
matching class taxonomy. The pose asset is required only if pose is enabled.
There are no remaining verified code blockers for the supported baseline.
Module 04 rack-relative ROTATING remains an existing unsupported feature;
Module 05's configured rotation rule is independently packet-tested, without
claiming upstream rotation support. Real labelled-session evaluation remains
an empirical follow-up; GUI/streaming/final application modules were not expanded.

## Files changed

The table below lists every repaired or newly added source/documentation file.
Generated ignored test logs/fixtures and the pre-existing global log are excluded.
| Path | Reason |
| --- | --- |
| `01_perception_core/tests/test_camera.py` | Replace historical skipped capture tests with actual source/preparation tests. |
| `02_yolo/core/detector.py` | Make missing local YOLO weights actionable; preserve offline loader. |
| `02_yolo/inputs/opencv_source.py` | Use a high-resolution strictly increasing camera clock. |
| `02_yolo/models/README.md` | Synchronize documentation with actual baseline behavior and absent local assets. |
| `02_yolo/pipeline.py` | Disable localhost semantic inference by default for the SIH path. |
| `02_yolo/tests/test_auto_enable.py` | Preserve explicit semantic extension tests and verify offline SIH default. |
| `03_optimization/README.md` | Synchronize documentation with actual baseline behavior and absent local assets. |
| `03_optimization/pipeline.py` | Pass source timestamps to the optional pose adapter while retaining legacy injection. |
| `03_optimization/pose/pose_tracker.py` | Adapt the existing local body helper to canonical Module 03 observations. |
| `03_optimization/tests/test_pose_helper.py` | Test helper lifecycle, timestamps and missing assets with injected inference. |
| `05_perception_fusion/DEFINITION_OF_DONE.md` | Synchronize documentation with actual baseline behavior and absent local assets. |
| `05_perception_fusion/PIPELINE.md` | Synchronize documentation with actual baseline behavior and absent local assets. |
| `05_perception_fusion/README.md` | Synchronize documentation with actual baseline behavior and absent local assets. |
| `05_perception_fusion/__init__.py` | Expose the canonical fusion entry point. |
| `05_perception_fusion/config.py` | Validate local rule/threshold/weight/temporal configuration. |
| `05_perception_fusion/evidence/boundary_evidence.py` | Normalize quality-gated confirmed boundary states. |
| `05_perception_fusion/evidence/contact_evidence.py` | Extract quality-gated positive contact evidence. |
| `05_perception_fusion/evidence/gesture_evidence.py` | Extract confirmed scored gesture evidence. |
| `05_perception_fusion/evidence/interaction_evidence.py` | Select current target-index interaction evidence using configured priority. |
| `05_perception_fusion/evidence/motion_evidence.py` | Consume actual calibrated rack-relative object velocity. |
| `05_perception_fusion/evidence/object_evidence.py` | Select a unique current stable non-context target. |
| `05_perception_fusion/fusion/confidence_fusion.py` | Aggregate only available supporting source scores. |
| `05_perception_fusion/fusion/conflict_resolver.py` | Record/suppress disagreement or prefer confirmed boundary by policy. |
| `05_perception_fusion/fusion/evidence_fusion.py` | Score configurable ordered all/any evidence rules. |
| `05_perception_fusion/har/activity_event_builder.py` | Build the shared event/result with identity, evidence and emission state. |
| `05_perception_fusion/har/activity_labels.py` | Read the configured activity vocabulary. |
| `05_perception_fusion/har/activity_recognizer.py` | Select rule candidates or unknown deterministically. |
| `05_perception_fusion/input/fusion_synchronizer.py` | Reject cross-frame/operator/time packet pairings. |
| `05_perception_fusion/input/packet_validator.py` | Validate shared nested contracts, statuses and confidence ranges. |
| `05_perception_fusion/pipeline.py` | Implement the authoritative deterministic Module 05 orchestrator. |
| `05_perception_fusion/temporal/activity_confirmation.py` | Implement target-isolated N-of-M confirmation and continuous-event deduplication. |
| `05_perception_fusion/temporal/evidence_buffer.py` | Keep bounded frame-keyed support without inventing missing hits. |
| `05_perception_fusion/tests/conftest.py` | Provide synthetic canonical upstream packets without model assets. |
| `05_perception_fusion/tests/test_activity_event.py` | Replace skipped scaffold tests with temporal/event regression coverage. |
| `05_perception_fusion/tests/test_conflict_resolution.py` | Replace skipped scaffold tests with actual conflict-policy coverage. |
| `05_perception_fusion/tests/test_evidence_fusion.py` | Replace skipped scaffold tests with validation, rule, confidence and rack-motion tests. |
| `06_pose_tracking/models/README.md` | Synchronize documentation with actual baseline behavior and absent local assets. |
| `MODULES_01_05_ARCHITECTURE.csv` | Classify every relevant Python implementation, wrapper, legacy file, test and scaffold. |
| `MODULES_01_05_REPAIR.md` | Record architecture, commands, evidence, limitations, deployment gates and all changes. |
| `README.md` | Synchronize documentation with actual baseline behavior and absent local assets. |
| `configs/fusion.yaml` | Replace null scaffold settings with configurable prototype activity rules. |
| `configs/pipeline.yaml` | Reference existing owner configs once for the real runner. |
| `conftest.py` | Create the generated test temp parent in fresh checkouts. |
| `fusion/__init__.py` | Expose Module 05 through a stable import-safe locator. |
| `integration/cli.py` | Implement shared source/config/lifecycle, JSONL diagnostics and event runners. |
| `integration/milestone.py` | Extend the real 01–03 chain through actual boundary processing and fusion. |
| `integration/sources.py` | Adapt existing local capture to shared FramePackets and driver metadata. |
| `integration/synthetic.py` | Provide synthetic pixels and inference-only scripted backends. |
| `models/README.md` | Synchronize documentation with actual baseline behavior and absent local assets. |
| `pose_tracking/__init__.py` | Expose the existing optional body helper without test-order bootstrap. |
| `procedures/demo_experiment.yaml` | Align example expected activities with the real fusion vocabulary. |
| `pytest.ini` | Stabilize collection and select writable isolated test fixtures. |
| `scripts/_bootstrap.py` | Share the direct-script repository import boundary. |
| `scripts/run_camera.py` | Replace scaffold with actual capture/preparation launcher. |
| `scripts/run_fusion.py` | Replace scaffold with genuine Modules 01–05 launcher. |
| `shared/schemas/activity_event.py` | Add optional provenance/confirmation/emission metadata to the existing contract. |
| `tests/test_full_pipeline.py` | Verify runnable milestone, events, diagnostics, errors and Ctrl+C cleanup. |
| `tests/test_fusion_integration.py` | Verify actual upstream contracts, offline rack data flow and FSM consumption. |
| `tests/test_local_inference_assets.py` | Add explicit real inference gates that skip only missing assets/dependencies. |
| `tests/test_procedure_runtime.py` | Use configured example activities in the existing FSM regression. |
