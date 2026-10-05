# MODULE 02 PROCEDURE + PIPER REPAIR REPORT

## Overall Status

**PARTIALLY REPAIRED** — F1, F3, F4, F5 and F6 fixed and regression tested. F2 real synthesis/playback and latency are blocked by Windows Application Control. Architecture unchanged; no commit/tag created.

Verified on 2026-10-05 using only the project .venv Python 3.11. Work estimate: about 85% of the repair requirements complete; this is an estimate, not a measured software metric.

## F1 — False Manipulate Action

- Root cause: taxonomy-valid but irrelevant incidental manipulation reached procedure validation.
- Fix: explicit procedure/action-object relevance filter before confirmation/fusion, with a second guard for externally confirmed events. Known action/object pairs on procedure objects that appear nowhere in the loaded procedure emit NON_PROCEDURAL_ACTION only.
- Correct yellow flow: PICK_YELLOW -> incidental MANIPULATE_YELLOW -> PLACE_YELLOW completes; incidental action does not change procedure index or produce a violation/voice warning.
- False warning: NONE in regression tests.
- Unknown actions, mismatched action/object pairs and unrelated objects remain eligible for unexpected-action validation.
- MANIPULATE_YELLOW remains in the taxonomy and can be required by another procedure.
- Tests use the actual classifier with injected tracked boxes, and separately test semantic/direct-event relevance. These are not physical operator accuracy tests.

## F3 — Manipulate Semantics

- Old rule: displacement outside home counted as manipulation.
- New evidence: persistent tracked object has already left home, enters the configured work ROI, dwells for consecutive work_dwell_frames (default 3), and moves at least displacement_threshold from its work-entry anchor inside that ROI. Procedure confirmation_frames still applies.
- Leaving work, a missing frame or changed track identity clears dwell evidence. Ordinary carrying outside work is UNCERTAIN.
- Work ROI: source-normalized x1,y1,x2,y2; each object's home/work interiors cannot overlap; both retain usable interior after boundary margin. Names must match configured action objects.
- Correct manipulation: full five-step actual-classifier regression completes with work-zone evidence.
- Skip manipulation: pick -> carry outside work -> return home produces one SKIPPED_STEP, leaves MANIPULATE_RED authoritative, and queues one warning without Qwen.
- Home-only legacy configurations retain PICK/PLACE support and report manipulation as unsupported.

## F2 — Real Piper

- Package/version: piper-tts 1.8.0; sounddevice 0.5.6; onnxruntime 1.30.0.
- Voice: en_US-lessac-medium, local English eSpeak voice.
- Model: C:/Users/lalit/AppData/Local/ORBITA/voices/en_US-lessac-medium.onnx (63,201,294 bytes).
- Matching configuration: same filename plus .json (4,885 bytes).
- Model SHA-256: 5efe09e69902187827af646e1a6e9d269dee769f9877d17b16b1b46eeaaf019f.
- Configuration SHA-256: efe19c417bed055f2d69908248c6ba650fa135bc868b0e6abb3da181dab690a0.
- Development setup used the declared requirements and documented piper.download_voices command. Assets are outside the repository; runtime never downloads.
- Actual model loading: PASS.
- Real synthesis: FAIL — importing espeakbridge raises "An Application Control policy has blocked this file."
- Real playback: NOT INVOKED; no Piper PCM was successfully produced. The explicit readiness smoke command was attempted, but no readiness speech was played.
- Error reporting repaired: WAV header cleanup no longer masks the native DLL failure with "channels not specified."
- Offline: architecture and local assets preserved; no cloud or runtime download.
- Required external resolution: machine policy owner must approve the trusted Piper native component. No attempt was made to bypass Application Control.

## Real Warning Latency

- Clock: shared injectable host time.perf_counter().
- T0: confirmed violation, before deterministic validator/queue processing.
- T1: host-domain estimate of first non-silent PCM reaching device DAC.
- PortAudio DAC/currentTime relative delta is added to perf_counter in the callback, then adjusted for leading PCM silence. Absolute clocks are not mixed.
- Benchmark now routes injected confirmed actions through ProcedureValidator -> AlertManager -> real Piper cache/synthesis -> playback. Cold mode includes startup/cache preparation; dynamic mode intentionally removes cached PCM.
- Requested: 3 cold, 10 warm cached, 3 dynamic samples.
- Completed valid samples: cold 0; warm cached 0; dynamic 0.
- Cold min/median/p95/max: NOT VERIFIED.
- Warm min/median/p95/max: NOT VERIFIED.
- Dynamic min/median/p95/max: NOT VERIFIED.
- <=1500 ms: NOT VERIFIED.
- REAL PIPER LATENCY NOT VERIFIED. DAC onset is an estimate; acoustic onset would additionally require external recording. Mock timings are not performance results.

## F4 — Clock

- Before: time.monotonic host timing.
- After: alerts.timing.host_time wraps time.perf_counter; confirmation, validator, queue, manager and default playback share it.
- Tests verify perf_counter delegation, injected clock propagation and correct relative PortAudio delta plus silence offset.

## F5 — Reset

- Old behavior: cancelled old-generation _active prompt suppressed an identical new prompt.
- New behavior: reset cancels playback and clears the active duplicate key, queue, cooldown and latency; generation guards still reject stale callbacks.
- New-generation prompt accepted: PASS while old cancelled playback is still returning.
- Regression checks exactly one new-generation audio-start publication, no duplicate/cooldown rejection.

## F6 — Missing Fast Config

- Startup emits console WARNING and JSONL fast_path_uncalibrated for missing or partial calibration.
- Warning explicitly states Qwen-dependent procedure warnings may exceed 1.5 s and recommends --fast-config with home/work ROIs.
- Console/log fast_path_coverage reports each required action YES/NO. Sample configuration covers all five required actions; missing config reports all NO.
- README documents target applicability, work evidence, legacy coverage, validation and slow Qwen-only confirmation.
- Actual CLI invocation without --fast-config confirmed warning, coverage log, successful PNG output and continued YOLO.

## Correct Procedure Test

Actual fast classifier, injected chronological tracked boxes, mocked TTS/playback:
- PICK_RED: STEP_COMPLETED.
- MANIPULATE_RED: STEP_COMPLETED only after work evidence and confirmation.
- PLACE_RED: STEP_COMPLETED.
- PICK_YELLOW: STEP_COMPLETED.
- PLACE_YELLOW: STEP_COMPLETED.
- Procedure: COMPLETED; false alerts: 0, including incidental yellow work/carry movement.
- This is deterministic classifier/assistant verification, not real camera action recognition.

## Skip Test

- Sequence: home -> pick -> carry outside work -> return/place.
- Violation: one SKIPPED_STEP; MANIPULATE_RED remains expected.
- Voice: one queued and mock-played warning.
- Real Piper speech: blocked as above.
- Qwen required: NO.

## Wrong-Order Test

- Sequence: PICK_YELLOW first while PICK_RED expected, then continued yellow carry/work movement.
- Violation: one WRONG_ORDER, no secondary UNEXPECTED_ACTION for incidental manipulation.
- Voice: one queued and mock-played warning.
- Procedure advancement: NONE.
- Real operator/speaker demonstration: not verified.

## Failure Isolation

- Actual native CLI with localhost:1: OLLAMA_UNAVAILABLE; YOLO and procedure/render/logging continue.
- Actual configured Piper blocked: VOICE_UNAVAILABLE with precise DLL reason; video and events continue.
- Real best.pt/ByteTrack check: same persistent ID 1 across 12 frames; assistant consumed actual detections without advancing on stationary evidence.
- Real full Module 01 -> Module 02 -> Module 03 and source-coordinate nonmutating rendering: PASS.
- Real standalone image/video and isolated copied package with SIH imports/all outbound network forbidden: PASS.
- Native procedure MP4: 4 readable frames, 320x436 with procedure panel. PNG and saved panel inspected.
- Existing bounded queue, priority, cooldown, reset/reuse and semantic event tests pass.
- Actual local Qwen smoke: READY, structured PLACE_RED response. Synthetic images verify execution/schema, not action accuracy.

## Module 01

Changes: NONE. Runtime, preprocessing and shared contracts untouched.

## Module 03

Runtime changes: NONE. Integration regression passes.

## ObjectFrame

Changed: NO. Procedure, semantic and voice outputs remain side outputs.

## Tests

Actual baseline: Module 02 241 passed; repository 395 passed, 99 skipped.
Final: Module 02 256 passed; repository 410 passed, 99 skipped.

New regressions:
- yellow pick/carry/place relevance through actual classifier;
- direct and semantic incidental relevance;
- another procedure legitimately requiring yellow manipulation;
- full five-step work-zone sequence;
- direct carry/place skip without Qwen;
- dwell requires motion and consecutive evidence;
- malformed work/legacy coverage;
- missing/partial calibration warnings and log coverage;
- unusable ROI interior;
- perf_counter abstraction/default clock propagation;
- reset active prompt accepts identical new-generation prompt;
- native synthesis error preserved;
- parametrized correct/skip/wrong-order fast classifier with mocked audio, one error per physical candidate.

Verification commands actually executed (all Python commands use .venv/Scripts/python.exe):
- -m pytest 02_yolo/tests --basetemp <scratch>/final-unit -q -p no:cacheprovider
- -m pytest --basetemp <scratch>/final-full -q -p no:cacheprovider
- -m ruff check 02_yolo
- -m ruff format --check 02_yolo
- -m yolo.tests.verify_types
- -m compileall -q 02_yolo
- -m yolo --help; -m 02_yolo --help (separate invocations)
- 02_yolo/tools/verify_runtime.py with ORBITA_VERIFY_DIR=<scratch>/native
- ollama list; 02_yolo/tools/smoke_semantic.py (separate invocations)
- 02_yolo/tools/benchmark_alert_latency.py --piper-model <local voice> --smoke-only --jsonl <scratch>/piper-smoke.jsonl
- 02_yolo/tools/benchmark_alert_latency.py --piper-model <local voice> --samples 10 --cold-samples 3 --dynamic-samples 3 --jsonl <scratch>/piper-latency.jsonl
- -m 02_yolo --source <scratch>/native/input.mp4 --procedure 02_yolo/examples/red_yellow_procedure.md --fast-config 02_yolo/examples/demo_fast_rules.yaml --piper-model <local voice> --ollama-host http://localhost:1 --no-display --output <scratch>/procedure-output.mp4 --events-jsonl <scratch>/procedure-events.jsonl
- -m 02_yolo --source <scratch>/native/input.png --procedure 02_yolo/examples/red_yellow_procedure.md --no-voice --no-vlm --no-display --output <scratch>/no-fast-output.png --events-jsonl <scratch>/no-fast-events.jsonl
- git diff --check; git diff --name-only -- perception 01_perception_core shared 03_optimization optimization; git diff --cached --name-only; git status --short (separate invocations).

Scratch: C:/Users/lalit/AppData/Local/Temp/orbita-procedure-repair-m8jq5o68.
Direct project-venv native API checks also verified model load, DLL failure, dependency versions, actual detector/assistant stationary frame handling and readable output dimensions.

## Static Checks

- Ruff: PASS.
- Format: PASS, 101 source files already formatted.
- Type: PASS, no issues in 48 source files.
- Compileall: PASS.
- Diff check: PASS. Git CRLF conversion notices are informational.
- Targeted tests initially hit the existing Windows default pytest temp-directory ACL; explicit unique --basetemp outside the repository resolved that setup issue. No tests suppressed to conceal failures.

## Files Changed

This repair pass changed existing files:
- 02_yolo/README.md
- 02_yolo/standalone_cli.py (fast-config help only)
- 02_yolo/alerts/manager.py
- 02_yolo/alerts/piper_tts.py
- 02_yolo/alerts/playback.py
- 02_yolo/procedure/assistant.py
- 02_yolo/procedure/fast_actions.py
- 02_yolo/procedure/fusion.py
- 02_yolo/procedure/validator.py
- 02_yolo/examples/demo_fast_rules.yaml
- 02_yolo/tests/test_alerts.py
- 02_yolo/tests/test_procedure.py
- 02_yolo/tools/benchmark_alert_latency.py

Added:
- 02_yolo/alerts/timing.py
- 02_yolo/procedure/relevance.py
- 02_yolo/tests/test_procedure_repair.py
- 02_yolo/PROCEDURE_PIPER_REPAIR_REPORT.md

No files removed. Models/best.pt, MODEL_MANIFEST.md and requirements-voice.txt unchanged.

Existing work was already uncommitted at entry: README, standalone_cli and tests/verify_types modified; prior procedure/alerts/examples, requirements-voice, tests, overlay and initial report untracked. That existing state was preserved; tests/verify_types was not edited in this repair. No root WAV/MP4/JPG or scratch directories added. No automatic commit/tag. Voice assets remain outside the repository.

## Remaining Limitations

Real Piper synthesis/playback/latency remains blocked by Application Control; F2 is OPEN. Hardware-policy approval and rerunning the real benchmark are required before claiming readiness/<=1500 ms. No synthesized replacement audio or fabricated latency was used.

Real operator action accuracy, physical camera demo, representative footage, rotation testing, microgravity, CUDA, FPS and semantic accuracy remain unverified. Work ROI motion/dwell is a calibrated demo proxy, not proof of manipulation/grasp physics. Qwen is still default-on, asynchronous and event-triggered; warnings relying on Qwen can take several seconds. Prototype is not flight- or safety-certified.

MODULE 02 PROCEDURE + PIPER STILL REQUIRES REPAIR

