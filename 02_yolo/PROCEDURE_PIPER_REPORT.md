# MODULE 02 PROCEDURE + PIPER UPDATE RESULT

## Status

PARTIALLY COMPLETE. The implementation and software verification pass. Real Piper playback and actual warning-start latency are NOT VERIFIED: this environment has no installed Piper package/executable or configured local voice/model JSON. No assets were downloaded. The requested <=1500 ms target cannot be claimed until the supplied benchmark is run with real local assets on the demo machine.

## Architecture

```text
Existing PreparedFrame / standalone adapter -> SAME DetectorPipeline
                                                  -> ObjectFrame -> Module 03
                                                  -> source-copy renderer
                                                  -> existing async event-triggered Qwen

Standalone --procedure:
strict Markdown -> ProcedureDefinition -> deterministic ProcedureValidator
Object observations -> opt-in calibrated FastClassifier -> consecutive confirmation
                                                       -> validator -> alert manager
                                                       -> next-step side output / HUD
Qwen SemanticResult -> distinct-event confirmation / conservative fusion -> future state
Alert manager -> single bounded worker -> load-once Piper -> cached PCM -> PortAudio
```

Procedure/alerts packages are isolated for later extraction into official FSM/alert modules. Detector inference, tracking, semantic worker, source-coordinate restoration and shared schemas were not changed. Qwen is absent from the fast warning path.

## Module 01

Changes: NONE. Git diff for perception/, 01_perception_core/ and shared/ is empty.

## Module 03

Runtime changes: NONE. Git diff for optimization/ and 03_optimization/ is empty. Real full-chain smoke passed.

## ObjectFrame

Contract changed: NO. ProcedureState, ProcedureEvent, ConfirmedAction and AlertEvent are separate outputs.

## Markdown Procedure

Deterministic bounded line parser; strict # Experiment / numbered ## Step sections. Required fields: id, action, object, instruction, warning, confirmation_frames. Optional timeout_ms. UTF-8/Unicode instructions supported. Exact action-object mapping comes from existing semantic configuration. No LLM parsing.

Sample: examples/red_yellow_procedure.md. Duplicate IDs/numbers/fields, missing fields, unknown actions, empty text, wrong objects, malformed sections and invalid confirmation/timeout integers fail before detector/input initialization. Maximum 64 steps/64 KiB. NONE and UNCERTAIN are not executable steps.

## Procedure Validator

- Correct: complete only the expected step and suggest the next instruction.
- Later same-object action: SKIPPED_STEP, with intervening step IDs; no advance.
- Later different-object action: WRONG_ORDER; no advance.
- Completed action: REPEATED_ACTION, no error voice.
- Other actionable labels outside the procedure: UNEXPECTED_ACTION.
- NONE/UNCERTAIN: no progression.
- Timeout: only when explicitly configured; once per expected step, based on monotonic wall time.
- Reset: return to the first step and clear action/fusion/voice generation state.

## Fast Action Path

Input: original-source-coordinate detections with unique persistent track identity. Rules are explicitly enabled by calibrated normalized home ROI YAML. Home -> outside is a PICK demo candidate; outside -> home is PLACE; off-home displacement magnitude is MANIPULATE. Per-step consecutive-frame confirmation is enforced. Absence, occlusion, lost/new identity, ambiguous classes/actions and boundary jitter do not become PICK. Optional rack reference rejects reference motion/loss.

No camera-up/gravity rule exists. Without calibrated ROIs, fast actions remain UNCERTAIN. These are supported demo transitions, not validated grasp/release semantics. They assume a fixed/calibrated scene and operator manipulation; camera/object motion can invalidate those assumptions. Real physical PICK/PLACE reliability is not established.

## Qwen Path

Model: qwen3-vl:2b-instruct. Existing default-on local Ollama branch remains asynchronous/event-triggered and bounded. Blocking fast alerts: NO. Ambiguous fast evidence can be refined using multiple distinct chronological READY semantic results; the same event cannot vote repeatedly on display frames. Stale/disagreeing results cannot retract fast commits or cause retroactive speech. Disagreements are logged. No calibrated score is introduced.

## Piper

Backend implemented against maintained PiperVoice.load/synthesize_wav Python API, with lazy imports and strictly local .onnx plus matching .onnx.json. Initial backend accepts English eSpeak voices to avoid auxiliary language-model downloads. Optional setup dependencies are in requirements-voice.txt. Existing sounddevice 0.5.6 and physical output devices were discovered, but no Piper voice/backend was available for actual speech.

One worker loads the voice once, deduplicates and pre-synthesizes procedure messages before READY. Cache defaults: 512 entries / 64 MiB, immutable PCM16 clips <=20 seconds. Critical cached clips are pinned; dynamic cache misses synthesize on the worker and are separately logged. Cache is memory-only and procedure-scoped, released on close, retained on reset. No temporary audio files or runtime download/install calls.

Voice unavailable/error degrades only audio. Unit tests mock the Piper/audio boundary; load-once and cached runtime playback are verified there, not falsely claimed as real model execution.

## Alert Policy

Examples:

- Wrong order: "Wrong order. Manipulate the red box."
- Skipped step: "Step 2 was skipped. Manipulate the red box before placing it."
- Next step: "Next step. Place the red box back."

Errors ON, next-step voice ON, success OFF. Default keyed cooldown is 2500 ms. One eight-entry queue coalesces duplicates. Errors supersede queued lower-priority speech and can cancel an active informational prompt. Full queues reject/coalesce unless lower-priority work can be displaced. Generation checks prevent reset/close callbacks from publishing stale latency.

## Latency

T0: monotonic violation-confirmation time after required multi-frame confirmation. T1: first non-silent audio output onset. Logs include confirmation, queued and playback-start timestamps plus warning_start_latency_ms.

Playback instrumentation maps PortAudio outputBufferDacTime to monotonic time and accounts for leading PCM silence. It identifies itself as a device-clock estimate; it is not acoustic microphone verification or queue-only timing.

Actual measured sample count: 0. Minimum, median, p95, maximum: NOT VERIFIED. Target <=1500 ms: NOT VERIFIED. Preferred <=1000 ms: NOT VERIFIED. No mock timing is reported as machine performance.

The real smoke invocation of benchmark_alert_latency.py --smoke-only returned NOT VERIFIED / VOICE_UNAVAILABLE / samples 0. It did not synthesize or play fake speech. Supply local assets, wait for VOICE READY and run the benchmark. Cold warm-up, queued speech and dynamic synthesis are included in measured delays and can exceed the target.

## Real Demo Tests

- Injected procedure/FSM tests: correct sequence through completion, skip Step 2 after Step 1, wrong-order later action first, repeat, unexpected action, timeout and reset all pass. These are not camera perception claims.
- Injected detector + slow-verifier integration: fast PICK then early PLACE confirms a skip and reaches the mocked audio-start callback while the semantic request is still blocked. No Qwen dependency in warning path.
- Real YOLO: existing local best.pt image/video, tracking IDs [[1], [1], [1], [1]], full 01/02/03 integration and copied standalone isolation passed. Network was prohibited during the existing offline smoke.
- Native procedure CLI: real four-frame YOLO video, default VLM READY, procedure state/HUD/event JSONL, voice-unavailable fallback and four decoded annotated frames of shape 436x320x3. No operator action was inferred or fabricated from insufficient evidence. Output was visually inspected.
- Final copied-package procedure-mode smoke: four real-YOLO video frames and procedure side outputs passed outside the repository with all shared/Module 01/Module 03 imports and all network connections forbidden. Voice absence remained isolated.
- Real Qwen: existing local smoke returned structured READY / PLACE_RED / red_box. Functional execution only; semantic correctness not measured.
- Real Piper playback: NOT RUN successfully; required local package/voice assets absent. Actual warning onset target remains unverified.

Artifacts: C:/Users/lalit/AppData/Local/Temp/orbita-procedure-vmzxk327, outside the source module.

## Test Results

Baseline: Module 02 195 passed; repository 349 passed, 99 skipped.

After extension: Module 02 241 passed; repository 395 passed, 99 skipped. Final suites used -W error and completed without warnings/failures. Added 31 procedure cases and 15 alert cases.

Actual final commands:

```powershell
.\.venv\Scripts\python.exe -m pytest 02_yolo/tests --basetemp C:\Users\lalit\AppData\Local\Temp\orbita-procedure-vmzxk327\unit-final -q -W error
.\.venv\Scripts\python.exe -m pytest --basetemp C:\Users\lalit\AppData\Local\Temp\orbita-procedure-vmzxk327\full-final -q -W error
.\.venv\Scripts\python.exe -m ruff check 02_yolo
.\.venv\Scripts\python.exe -m ruff format --check 02_yolo
.\.venv\Scripts\python.exe -m yolo.tests.verify_types
.\.venv\Scripts\python.exe -m compileall -q 02_yolo
.\.venv\Scripts\python.exe -m 02_yolo --help
.\.venv\Scripts\python.exe 02_yolo/tools/benchmark_alert_latency.py --smoke-only
.\.venv\Scripts\python.exe 02_yolo/tools/smoke_semantic.py
```

Existing verify_runtime.py was run with ORBITA_VERIFY_DIR pointing to the above temporary runtime subdirectory. Native procedure video command was run with --source <runtime/input.mp4>, --procedure examples/red_yellow_procedure.md, --fast-config examples/demo_fast_rules.yaml, --no-display, --output, --jsonl and --events-jsonl, without disabling VLM or voice. Source/output files stayed outside the repository.

## Static Checks

Ruff: PASS. Format: PASS, 97 files. Type check: PASS, 46 source files. Compileall: PASS. CLI help: PASS. Git whitespace check: PASS. No model assets were changed. No commits or tags created.

## Files Added

- procedure/__init__.py
- procedure/contracts.py
- procedure/markdown_loader.py
- procedure/validator.py
- procedure/fast_actions.py
- procedure/fusion.py
- procedure/event_log.py
- procedure/assistant.py
- alerts/__init__.py
- alerts/contracts.py
- alerts/audio_cache.py
- alerts/piper_tts.py
- alerts/playback.py
- alerts/manager.py
- examples/red_yellow_procedure.md
- examples/demo_fast_rules.yaml
- requirements-voice.txt
- tests/test_procedure.py
- tests/test_alerts.py
- tools/benchmark_alert_latency.py
- visualization/procedure_overlay.py
- PROCEDURE_PIPER_REPORT.md

All paths above are under 02_yolo/.

## Files Changed

- 02_yolo/standalone_cli.py: opt-in assistant/voice flags, separate JSONL state/events and display side branch.
- 02_yolo/tests/verify_types.py: include procedure/alerts runtime packages.
- 02_yolo/README.md: schema, rules, setup, usage, latency and limitations.

## Remaining Limitations

Piper package/voice setup and real playback/latency measurement remain required. Physical webcam, real operator footage, CUDA, fast PICK/PLACE semantic accuracy, Qwen accuracy and rotated demonstrations were not tested here. Ground rotation demonstrations would not prove microgravity behavior. The procedure assistant is a hackathon prototype, not flight- or safety-certified.

MODULE 02 PROCEDURE ASSISTANT REQUIRES REPAIR
