# MODULE 02 VLM AUTO-ENABLE UPDATE

## Status

COMPLETE. Verified on 2026-10-05 using the repository `.venv/Scripts/python.exe`.

## Default Before

YOLO: ON. Tracking: ON. VLM: OFF.

## Default After

YOLO: ON. Tracking: ON. VLM: ON, with optional availability and event-triggered inference.

## Config Change

| File | Field | Before | After |
|---|---|---|---|
| config/semantic.yaml | semantic.enabled | false | true |
| semantic/contracts.py | SemanticConfig.enabled | False | True |

Changing both defaults covers the typed default used by standalone and SIH constructors, as well as explicitly loaded YAML. No duplicate configuration keys were introduced.

## CLI Behavior

Normal startup enables semantics without `--vlm`. Existing `--no-vlm` disables it completely: no worker, availability probe or inference request. Existing `--vlm` explicitly enables it, including overriding a disabled YAML. API callers can pass `SemanticConfig(enabled=False)`.

```powershell
.\.venv\Scripts\python.exe -m 02_yolo --source demo.mp4
.\.venv\Scripts\python.exe -m 02_yolo --source demo.mp4 --no-vlm
```

## Ollama Behavior

The existing semantic worker performs a startup `/api/tags` availability probe without blocking the YOLO thread. It publishes the existing READY, MODEL_MISSING or OLLAMA_UNAVAILABLE status, but no SemanticResult or chat request from availability alone. WAITING is valid while the probe is pending. Unexpected optional verifier failures become VLM_ERROR.

No daemon startup, model pull, remote host, cloud API, proxy or redirect support was added. Host remains http://localhost:11434 and model remains qwen3-vl:2b-instruct. Existing 10-second retry cache and 30-second default request timeout remain unchanged.

## Event Trigger

Qwen per-frame: NO. Qwen event-triggered: YES. Direction-independent trigger, three-second cooldown, eight-JPEG buffer, sampling every second accepted frame, maximum four keyframes and one pending/in-flight event are unchanged. The startup availability probe uses the same worker and serialized verifier lock. Generation checks prevent a late startup probe from overwriting reset/closed state, and a busy event status cannot be overwritten by probe completion.

## Module 01

Runtime, preprocessing, public APIs and contracts: NONE changed.

## Module 03

Runtime changes: NONE. Shared ObjectFrame integration: PASS.

## ObjectFrame

Contract changed: NO. SemanticResult remains separate. Source-coordinate boxes and rendering on copied source pixels remain unchanged.

## Real Runtime

- `ollama list` confirmed qwen3-vl:2b-instruct installed locally.
- Existing real semantic smoke returned READY with structured PLACE_RED/red_box. This proves execution/schema compatibility, not correctness of that interpretation.
- Actual `python -m 02_yolo --source ...` without an enable flag produced READY on a real detected image with track ID 1.
- Actual default CLI video processed 400 frames, with detector errors 0, tracked observations in 400 frames, and two completed MANIPULATE_RED semantic events anchored to sampled frames 30 and 190. This synthetic fixture does not measure semantic accuracy. Pending events at shutdown retain the existing discard behavior.
- Annotated MP4 decoded to all 400 frames. Inspected its completed-event overlay at display frame 170: current frame and last semantic event/frame/time were distinguishable.
- A separate live Module 01 -> PreparedFrame -> default-enabled Module 02 -> shared ObjectFrame -> Module 03 run had VLM READY, track IDs [[1], [1], [1], [1]], and unchanged source/prepared pixels after rendering.
- Existing runtime tool passed real image/video, integrated output, reset, tracking and copied-package independence with all network blocked. When that guard rejects even localhost using AssertionError, semantic status is VLM_ERROR; detector operation still passes.

Artifacts are outside source in:
`C:/Users/lalit/AppData/Local/Temp/orbita-auto-vlm-0ee9_zv_`.

## Failure Fallback

- Native 40-frame video pointed to unavailable loopback port 23114: OLLAMA_UNAVAILABLE throughout, detector errors 0, tracked observations in all 40 frames, UNCERTAIN result for sampled frame 30, and 40 readable annotated frames. Inspected the final overlay showing unavailable status and event provenance.
- Native image with nonexistent model name: MODEL_MISSING, while real YOLO and track ID 1 remained available.
- Native image with --no-vlm: DISABLED, with real YOLO and track ID 1.
- Unit tests verify disabled mode makes no Ollama calls; unavailable mode still emits shared ObjectFrame and renders without mutation.

## Tests Added/Updated

New test_auto_enable.py contains 13 parameterized cases:

- test_runtime_and_yaml_defaults_enable_semantics
- test_default_startup_checks_local_availability_without_inference
- test_default_sih_emits_objects_and_semantic_result_without_mutating_frames
- test_cli_preserves_enable_disable_overrides
- test_default_trigger_is_not_per_frame_and_reset_remains_enabled
- test_startup_probe_does_not_block_yolo_or_publish_stale_status
- test_default_qwen_worker_processes_events_after_close_reuse

Existing tests updated:

- test_disabled_semantics_never_contacts_ollama now explicitly selects disabled configuration.
- test_standalone_image_and_video_outputs now expects semantics active by default.
- test_semantic_pipeline_close_reuse_processes_new_event now relies on the enabled typed default instead of explicitly enabling it.
- Root integration test test_offline_chain_reuses_models_and_preserves_source mocks an unavailable local Ollama service while preserving its original prohibition on network connections. This is the sole change outside Module 02; it is a test fixture adaptation to startup probing, with no runtime impact or changed Module 01 behavior.

The 100-frame call-counter test verifies no more than four chats, all bounded to four keyframes, then verifies reset permits a new result. Default Qwen close/reuse produces two new events on distinct workers sharing the same verifier. Existing inflight-generation lifecycle tests still pass.

## Test Results

Baseline: 182 Module 02 tests passed; full repository 336 passed, 99 skipped.

Final: 195 Module 02 tests passed; full repository 349 passed, 99 skipped. Both final suites ran with warnings treated as errors, with no warnings or failures.

Actual final commands:

```powershell
.\.venv\Scripts\python.exe -m pytest 02_yolo/tests --basetemp C:\Users\lalit\AppData\Local\Temp\orbita-auto-vlm-0ee9_zv_\unit-approved -q -W error
.\.venv\Scripts\python.exe -m pytest --basetemp C:\Users\lalit\AppData\Local\Temp\orbita-auto-vlm-0ee9_zv_\full-approved -q -W error
```

## Static Checks

Actual verification commands:

```powershell
.\.venv\Scripts\python.exe -m ruff check 02_yolo tests/perception/test_review_regressions.py
.\.venv\Scripts\python.exe -m ruff format --check 02_yolo tests/perception/test_review_regressions.py
.\.venv\Scripts\python.exe -m yolo.tests.verify_types
.\.venv\Scripts\python.exe -m compileall -q 02_yolo
.\.venv\Scripts\python.exe -m yolo --help
.\.venv\Scripts\python.exe -m 02_yolo --help
```

Ruff: PASS. Format: 78 files formatted. Type verification: no issues in 31 source files. Compilation and both CLI help entry points: PASS.

Runtime commands actually executed included:

```powershell
ollama list
.\.venv\Scripts\python.exe 02_yolo/tools/smoke_semantic.py
$env:ORBITA_VERIFY_DIR='C:\Users\lalit\AppData\Local\Temp\orbita-auto-vlm-0ee9_zv_\runtime'
.\.venv\Scripts\python.exe 02_yolo/tools/verify_runtime.py
.\.venv\Scripts\python.exe -m 02_yolo --source C:\Users\lalit\AppData\Local\Temp\orbita-auto-vlm-0ee9_zv_\native-input.mp4 --no-display --output C:\Users\lalit\AppData\Local\Temp\orbita-auto-vlm-0ee9_zv_\native-annotated.mp4 --jsonl C:\Users\lalit\AppData\Local\Temp\orbita-auto-vlm-0ee9_zv_\native.jsonl
.\.venv\Scripts\python.exe -m 02_yolo --source C:\Users\lalit\AppData\Local\Temp\orbita-auto-vlm-0ee9_zv_\native-input.mp4 --max-frames 40 --ollama-host http://127.0.0.1:23114 --no-display --output C:\Users\lalit\AppData\Local\Temp\orbita-auto-vlm-0ee9_zv_\unavailable.mp4 --jsonl C:\Users\lalit\AppData\Local\Temp\orbita-auto-vlm-0ee9_zv_\unavailable.jsonl
```

Native image, missing-model and manual-disable variants, temporary media generation, output decoding, and live full-pipeline checks were also executed with the same .venv. No model was downloaded or modified.

## Files Changed

- 02_yolo/config/semantic.yaml
- 02_yolo/semantic/contracts.py
- 02_yolo/semantic/worker.py
- 02_yolo/standalone_cli.py
- 02_yolo/README.md
- 02_yolo/tests/test_extensions.py
- 02_yolo/tests/test_prefreeze.py
- tests/perception/test_review_regressions.py (integration test only)

Added:

- 02_yolo/tests/test_auto_enable.py
- 02_yolo/VLM_AUTO_ENABLE_REPORT.md

No model files, MODEL_MANIFEST.md, class maps or shared schema files changed. No commits, tags or staging operations were performed. Pre-existing untracked user media and tmp_pytest directories were preserved.

## Final Verification

Physical webcam and CUDA were not tested in this pass. FPS and semantic accuracy were not measured. Synthetic scenes do not prove interaction recognition. Rotation-based ground demonstrations only approximate orientation-agnostic behavior and do not prove microgravity performance. No flight certification is claimed.

DEFAULT VLM AUTO-ENABLE: PASS

MODULE 02 VLM AUTO-ENABLE UPDATE COMPLETE
