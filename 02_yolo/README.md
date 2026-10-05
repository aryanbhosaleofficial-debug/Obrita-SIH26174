# Module 02 ? Object & Semantic Perception

Module 02 performs offline YOLO object detection and optional tracking, supplies the unchanged SIH `ObjectFrame` to Module 03, and provides annotated images/video as a side output. Optional local Qwen3-VL produces **semantic candidates**, never procedure decisions or ground truth. Module 01, Module 03 and shared wire contracts are unchanged.

## Implemented architecture

```text
SIH: FramePacket -> Module 01 (unchanged) -> PreparedFrame
                                                |
                                       adapters.sih
                                                |
Standalone: OpenCV camera/image/video -> adapters.standalone
                                                |
                                      core.DetectorPipeline
                                      ONE Ultralytics adapter
                                      parser/filter/tracking
                                      source coordinate restoration
                                                |
                      +-------------------------+-------------------+
                      |                         |                   |
SIH constructors -> shared ObjectFrame   FrameRenderer       event trigger
          |                    source frame COPY               |
Module 03 (unchanged)          annotated image/video     bounded JPEG buffer
                                                              |
                                                     one local Ollama worker
                                                              |
                                                      SemanticResult side output
```

The reviewed algorithm was relocated into `core/pipeline.py`, `core/detector.py`, and `core/postprocess.py`. The old `pipeline.py` and `inference/*` entry points are compatibility facades. The SIH adapter supplies shared observation/result constructors and preserves exception types; standalone supplies Module 02-owned `InputFrame`, `DetectionFrame`, configuration and observation types. No competing detector exists. Legacy scaffold directories remain inactive.

YOLO owns class IDs, class names, bounding boxes, detector scores and backend track IDs every frame. Ultralytics reverses its own letterbox. Filtering, duplicate-ID rejection, prepared-to-source scaling, four-ULP boundary clamping, local class-map validation and tracker reset remain as reviewed. IDs are emitted only when the backend supplies them; Module 02 does not claim temporal confirmation or stabilize detections. Module 03 retains that ownership.

## Offline setup and model assets

Use Python 3.11+ and install dependencies **during setup**, before disconnecting the internet:

```powershell
python -m pip install -r 02_yolo/requirements.txt
# Only when the original HAR.zip is available:
python 02_yolo/tools/inspect_har.py
python 02_yolo/tools/extract_har_model.py
```

Use the root ORBITA OpenCV family: **opencv-contrib-python>=4.7**. Avoid installing opencv-python, opencv-contrib-python and their headless variants together: they share the cv2 namespace. The current environment contains both OpenCV wheels, so installed packages were left unchanged during freeze cleanup. In a fresh environment install one family; Ultralytics may pull opencv-python transitively. If both are present, explicitly uninstall both and reinstall only opencv-contrib-python during environment setup, then run the verification suite. This package-only repair is not part of normal runtime.

Install a CPU/CUDA Torch build appropriate for the host if necessary. Runtime loads existing local `.pt` or `.onnx` assets only. Never use an untrusted pickle checkpoint. The supplied `HAR/best.pt` was inspected statically before its explicitly authorized inference verification. The extraction tool selects that exact member, checks its size/SHA-256, refuses different existing weights, and never executes checkpoint code. `models/best.pt` is local and Git-ignored; [MODEL_MANIFEST.md](models/MODEL_MANIFEST.md) records current metadata, hash and a verified backup. HAR.zip is currently absent, so archive-inspection/extraction commands are optional historical setup only; distribute it explicitly with the copied module or use `--weights`. Do not silently fetch a model.

The ready-to-use local profile is `02_yolo/config/standalone.yaml`, with:

- `models/best.pt`: YOLOv8n detection model used by the prototype.
- Classes: `0 lid`, `1 main_box`, `2 red_box`, `3 yellow_box`.
- Threshold 0.50, IoU 0.45, auto device, local ByteTrack and no ReID downloads.

The existing repository `configs/yolo.yaml` and its class-map expectations are preserved. Choose the HAR profile explicitly in SIH mode when using these weights; its four classes differ from the old project placeholders. A model/class-map mismatch remains a fatal setup error.

## Standalone mode

From the repository root:

```powershell
.\.venv\Scripts\python.exe -m 02_yolo --source 0
.\.venv\Scripts\python.exe -m 02_yolo --source demo.mp4
.\.venv\Scripts\python.exe -m 02_yolo --source test.jpg
python -m yolo --source demo.mp4 --vlm
python -m yolo --source demo.mp4 --no-vlm --output annotated.mp4 --jsonl results.jsonl
python -m yolo --source test.jpg --no-display --output annotated.png
python -m yolo --source 0 --weights C:/models/best.pt --classes 02_yolo/config/har_classes.yaml --device cpu
```

OpenCV displays results; press Q or Escape to exit. A still image waits for a key. Console output is one JSON object per frame (detections, independent VLM status and last completed semantic result). `--jsonl` writes the same records. `--no-display` supports headless use. `--max-frames N` bounds camera/video runs. Camera identifiers are nonnegative integer strings; other sources must be existing local files. Network video URLs are rejected. Image output requires an image extension; camera/video output requires `.mp4`. The writer refuses frame-size changes.

Copy **the entire `02_yolo` directory** anywhere, with its local model/config assets and installed dependencies:

```powershell
cd C:/Temp/orbita_module02
python standalone.py --source 0
python standalone.py --source demo.mp4 --no-display --output annotated.mp4
python standalone.py --source test.jpg --no-vlm
```

The copied directory needs no top-level `yolo/` alias, Module 01, Module 03, shared package, perception, integration, FSM, voice or GUI application. `standalone.py` bootstraps the package alias locally. From its parent, `python -m orbita_module02 --source test.jpg` also works if that is the directory name. Existing repository `python -m yolo --input image.png --core-config configs/perception.yaml` retains the previous single-image SIH smoke path. It requires SIH modules by design; `--source` is the independent path.

## SIH pipeline mode and integrated rendering

```python
from yolo.config import load_config
from yolo.pipeline import YoloPipeline

# prepared is the existing Module 01 PreparedFrame.
with YoloPipeline(
    load_config("02_yolo/config/standalone.yaml"),
) as module02:
    objects = module02.process(prepared)  # exact shared ObjectFrame
    downstream = module03.process(prepared, objects)  # existing Module 03 API
    display = module02.render(prepared, objects)  # side branch only
    semantic = module02.semantic_result  # may be None / old event
```

Real applications keep the pipeline alive across frames rather than opening it for each frame. Semantics are enabled by default in standalone and SIH mode; use `--no-vlm` or `SemanticConfig(enabled=False)` to disable them. This does not alter `process()`'s return type. Module 03 receives the clean prepared/source frame and `ObjectFrame`. It never receives annotated pixels or Qwen output during this task. A custom backend injected into `YoloPipeline` must return **shared.schemas.observations.Detection** leaves with shared BoundingBox types; its diagnostics must use shared contracts too. Module-private core leaves belong to DetectorPipeline/standalone and are rejected at the SIH boundary with INVALID_OBSERVATION diagnostics. This does not weaken leaf validation or modify shared schemas.

Callers own `cv2.imshow` or video writing in integrated mode. No Module 01 rendering hook is required.

## Coordinates and frame ownership

`ObjectFrame` boxes are **absolute pixels of the original FramePacket image**, after exactly one inverse Module 01 scale conversion. `FrameRenderer` takes `prepared.source` in SIH mode and the standalone source frame in standalone mode. It validates dimensions, frame ID, timestamp, source and session against the result, converts original RGB/gray to display BGR as needed, and draws on a **copy**. A resized prepared image is rejected rather than silently drawing boxes in the wrong space. To render on a smaller display, render the original first and resize the completed display copy.

Overlays show bounding boxes, class, YOLO score, available track ID, frame ID, YOLO status, tracking status and VLM status. A semantic overlay identifies the **last semantic event**, event ID, sampled frame ID and timestamp, so a slow result cannot appear to refer to the current frame. Rendering errors are `VisualizationError`; detection results remain available independently. Neither original pixels nor prepared AI pixels are changed.

## Optional local Qwen3-VL

Install Ollama separately and download its model explicitly during setup:

```powershell
ollama pull qwen3-vl:2b-instruct
ollama serve
.\.venv\Scripts\python.exe -m 02_yolo --source 0
```

An already running local Ollama service does not need a second `serve`. After dependencies and models are installed, internet may be disconnected. The default host is `http://localhost:11434` and default model `qwen3-vl:2b-instruct`. Override with `--ollama-host`, `--vlm-model`, or `--semantic-config 02_yolo/config/semantic.yaml`. Only HTTP loopback hosts are allowed, proxies/redirects are disabled, and cloud aliases are rejected. Runtime calls `/api/tags` and `/api/chat`; it never calls a pull endpoint. There is no OpenAI, Claude, Gemini, remote Qwen or other cloud API.

The adapter follows Ollama's official [chat API](https://docs.ollama.com/api/chat), [local model listing](https://docs.ollama.com/api/tags), and [structured outputs](https://docs.ollama.com/capabilities/structured-outputs) contracts.

Availability is checked automatically at startup on the existing background worker, without blocking YOLO or submitting a semantic event, with retry caching (10 seconds by default). States distinguish `DISABLED`, `WAITING` (availability pending or semantic state reset), `BUSY`, `READY`, `MODEL_MISSING`, `OLLAMA_UNAVAILABLE`, `VLM_ERROR` and `VLM_PARSE_ERROR`. A connection error/timeout, missing model or parse failure emits `UNCERTAIN` with its own semantic failure status. **YOLO, tracking, ObjectFrame and rendering continue.** There is no automatic download or daemon startup.

### Event sampling and worker bounds

The default buffer holds at most eight detached JPEGs, samples every second accepted detector frame, selects at most four evenly spaced chronological keyframes, and downsizes each image to a 640-pixel maximum side. A JPEG is capped at 1 MiB; capacity is validated between 2 and 64. Observation snapshots carry class names, detector scores, track IDs and original-source boxes. The newest selected image's frame ID/timestamp anchors the semantic result.

The explainable trigger checks **direction-independent** object-center displacement normalized by image diagonal, appearance/disappearance or identity changes. Untracked duplicate classes are excluded from displacement matching. Default displacement threshold is 0.04 and cooldown is three seconds. Optional `interval_s` requests a configured interval; it is off by default. These are trigger thresholds, not physical action classifiers. Camera motion can trigger events. No image-axis gravity assumption is used.

There is one daemon worker and at most **one pending/in-flight event**, with no frame backlog. Events are skipped while busy, and fresh frames continue through YOLO. Default HTTP timeout is 30 seconds; response size is capped at 1 MiB. `context_tokens: 16384` is explicit because four images exceeded the installed Ollama default 4096-token context during verification. Larger settings may consume more RAM. No performance guarantee is made.

A single still image does not automatically request a temporal action label. Its VLM status is `WAITING` while the startup probe is pending, then the actual availability status (for example `READY` or `OLLAMA_UNAVAILABLE`); `READY` does not imply an action was inferred. A short video can finish before its VLM event completes. Shutdown discards those results instead of delaying the detector loop. Long live sessions show completed events on following frames.

### Semantic contract and validation

`SemanticResult` is frozen and owned by Module 02:

```text
action, object_name, status, timestamp_s, frame_id, event_id, reason
```

The default action-object allowlist preserves the prototype names:

```text
PICK_RED / PLACE_RED / MANIPULATE_RED       -> red_box
PICK_YELLOW / PLACE_YELLOW / MANIPULATE_YELLOW -> yellow_box
NONE / UNCERTAIN                          -> null
```

Set `action_objects` in semantic YAML or `SemanticConfig` for another experiment. Qwen receives ordered images, the allowlist, object observations and explicit orientation guidance. It returns exactly `{"action":"PICK_RED","object":"red_box"}` or another allowed pair. Parsing rejects duplicate keys, Markdown, free text, extra fields, unknown actions and inconsistent object names. Invalid output becomes `UNCERTAIN` / `VLM_PARSE_ERROR`. No arbitrary response text enters the semantic contract or FSM. There is no numeric VLM confidence/probability field.

## Configuration and reset

The existing detector-only YAML layout (`detector:`) is retained, with model/classes/tracker paths relative to that YAML. Confidence, IoU, whitelist, device, CPU fallback and tracking remain configurable. Semantic settings live in a separate `semantic:` YAML, leaving the shared DetectorConfig unchanged. `--vlm` / `--no-vlm` overrides `enabled`. See the provided config files for all practical defaults.

Upstream `reset_required` retains the reviewed tracking reset/retry behavior and clears the temporal buffer, trigger baseline, pending event and stale semantic output. Explicit `reset()` does the same. Generation tokens prevent an old in-flight response from publishing after reset or close. Loaded YOLO weights are preserved when the backend supports tracker reset. An already executing HTTP request cannot be forcibly canceled safely: it finishes/times out in the daemon, its output is ignored, and new semantic work waits until that one request finishes. A closed pipeline can be reused: successful initialize (explicitly or from process) creates a fresh semantic worker with the same configuration and verifier. Closed-generation results cannot publish. A shared verifier lock prevents overlapping verifier calls while the old request completes; YOLO initialization/processing does not wait for that request. Semantic events remain bounded and queued work waits for the retained verifier to become available.

YOLO initialization failures remain fatal setup errors. YOLO frame failures produce empty `ERROR` results; tracker reset failures are labeled `tracker_reset` in diagnostics. Tracked accelerator failure requires a coordinated reset; it never silently restarts IDs via CPU fallback. VLM failures degrade semantics only. Source errors and visualization errors have distinct exception types and CLI error messages. CLI returns 0 for successful operation, 1 for detector frame failures and 2 for setup/source/render failures. A VLM failure alone does not make a healthy detector run fail.

## HAR.zip migration audit

The historical audit recorded the archive contents below; HAR.zip is now absent. The current model is independently documented in models/MODEL_MANIFEST.md. The archive contained exactly `HAR/`, `HAR/main.py` (8,013 bytes), `HAR/best.pt` (6,249,770 bytes) and `HAR/weights.pt` (5,423,109 bytes). Inspection used ZIP listing, source text and `pickletools` disassembly, **not torch.load/unpickling** for metadata.

| File / component | Purpose | Classification | Destination |
|---|---|---|---|
| main.py YOLO("best.pt"), conf=0.45 | Local detector loop | ADAPT | Existing detector core retained; separate HAR profile uses reviewed 0.50 default |
| main.py ObjectTracker | Class-keyed y-center/aspect smoothing and debounce; not multi-object ID tracking | ADAPT concept | Bounded temporal buffer and direction-independent trigger; existing ByteTrack IDs retained |
| main.py PICK/PLACE/MANIPULATE heuristics | Upward displacement, table return and aspect change | DISCARD as action authority | No vertical-motion action rule ported |
| main.py drawing/capture | OpenCV rectangles, labels, webcam and HUD | ADAPT | inputs/opencv_source.py and visualization/renderer.py, drawing on copies |
| main.py ExperimentSequence | Ordered steps, advancement, wrong-order warning | MOVE ELSEWHERE (ownership only) | Remains reference material for external FSM; no sequencing code moved |
| main.py speak_async / pyttsx3 | Threaded voice prompts | MOVE ELSEWHERE (ownership only) | Alert layer responsibility; no voice code moved |
| best.pt | YOLOv8n DetectionModel, checkpoint Ultralytics 8.4.162; IDs 0 lid, 1 main_box, 2 red_box, 3 yellow_box | REUSE | Explicitly extracted once to models/best.pt |
| weights.pt | YOLO26n (yolo26n.yaml) DetectionModel, checkpoint 8.4.55; IDs 0 HAR, 1 Lid, 2 main_box, 3 red_box, 4 yellow_box | DISCARD from active configuration | Remains in archive; not used by main.py, not extracted or loaded |

`best.pt` SHA-256: `b9ab5c71a5c4e0ed151d6e8001983e5e7d5a5995a73cc419d580da304f1c687d`.
`weights.pt` SHA-256: `8884dd82cff5c497f59ae09a8076dc8d26dd12fbce59fa2dfbaafe40235c425a`.
Architecture/class labels are statically inspected checkpoint claims, and best.pt subsequently passed real local loading/inference. Weights.pt was not runtime validated. Nothing in the archive establishes action accuracy. Both carry Ultralytics AGPL metadata; consider applicable licensing when distributing them.

## Verification and limitations

Commands used (from repository root; the repository venv is shown):

```powershell
.\.venv\Scripts\python.exe -m pytest 02_yolo/tests tests/test_yolo_to_optimization.py -q -p no:cacheprovider
.\.venv\Scripts\python.exe 02_yolo/tools/inspect_har.py
.\.venv\Scripts\python.exe 02_yolo/tools/extract_har_model.py
.\.venv\Scripts\python.exe -m pytest 02_yolo/tests -q -p no:cacheprovider
.\.venv\Scripts\python.exe -m pytest -q -p no:cacheprovider
.\.venv\Scripts\python.exe 02_yolo/tools/verify_runtime.py
.\.venv\Scripts\python.exe 02_yolo/tools/smoke_semantic.py
```

The offline tests reject socket connections/DNS and mock Ollama responses. New tests cover both adapters, source-sized nonmutating visualization, actual Module 03 consumption, empty/mismatched frames, bounded/sampled chronology, direction-independent triggers, parser validation, configuration, unavailable Ollama/model, timeout/API/parse errors, bounded worker, reset races, camera structure, image/video writing and copying the module with forbidden SIH imports. The real runtime check blocks outbound networking, loads local weights, writes/reads a four-frame annotated MP4, verifies real backend ID persistence, passes Module 01 -> Module 02 -> Module 03 with a four-frame integrated annotated MP4 and runs copied standalone with no SIH imports. The original update results are in [UPDATE_REPORT.md](UPDATE_REPORT.md); current pre-freeze verification is in [PRE_FREEZE_REPORT.md](PRE_FREEZE_REPORT.md).

Ollama smoke uses synthetic chronological red-square images. Its response verifies local transport/model/schema execution only. Detection/action accuracy, calibrated confidence, representative FPS, latency benchmarks, GPU behavior and physical webcam/display operation were **not measured/verified**. Camera handling is structurally tested; real image/video inference and saved outputs were verified. OpenCV cannot reliably distinguish a mid-video decode error from EOF. Rendering is opt-in in SIH mode; runtime users choose their display/writer.

**Rotation-based ground demonstrations are only approximations of orientation-agnostic behavior and do not prove real microgravity performance.** A 2B VLM can make semantic mistakes. This is a hackathon prototype, with no flight certification, space qualification, microgravity validation, ISRO validation or safety certification. FSM sequencing, skipped steps, next-step suggestions, procedure validation and voice remain outside Module 02.

## Pre-freeze verification and temporary files

The configuration facade delegates to core.config; SIH config/result/exception types remain shared, while standalone keeps private contracts. The type verifier now checks all 31 active runtime files, rather than only the legacy facades:

```powershell
python -m yolo.tests.verify_types
python -m ruff check 02_yolo
python -m ruff format --check 02_yolo
python -m compileall -q 02_yolo
python -m yolo --help
python 02_yolo/standalone.py --help
```

Large .verification dependency caches and historical verification outputs/audit were relocated outside Module 02. New runtime smoke outputs default to a fresh OS temporary directory; set ORBITA_VERIFY_DIR explicitly to preserve them at a chosen location. Type-check temporary copies/caches also stay outside Module 02. If pytest's default temporary directory is inaccessible, use --basetemp with a **new, dedicated temporary path** rather than changing tests or frozen modules.

## Standalone procedure assistant and Piper voice

The optional standalone assistant lives in `yolo.procedure` and `yolo.alerts` for future extraction into the project's FSM/alert modules. DetectorPipeline, SIH adapters, Module 01, Module 03 and ObjectFrame are unchanged. No procedure state or voice fields enter ObjectFrame. Without `--procedure`, the existing detector CLI behaves as before.

```text
Markdown -> deterministic definition -> ordered validator
YOLO/track observations -> calibrated demo rules -> consecutive confirmation
                                             -> validator -> bounded voice queue
                                                          -> cached Piper PCM -> speaker
Qwen event results -> separate conservative confirmation/fusion -> future state
```

### Strict Markdown definition

See `examples/red_yellow_procedure.md`. The first nonempty line must be `# Experiment: NAME`. Consecutive `## Step 1`, `## Step 2`, ... sections each require exactly one of:

```markdown
# Experiment: Example

## Step 1
- id: pick_red
- action: PICK_RED
- object: red_box
- instruction: Pick up the red box.
- warning: Pick up the red box first.
- confirmation_frames: 3
- timeout_ms: 5000
```

`timeout_ms` is optional. Without it there is no time-based omission rule. `object: null` is supported only when the configured actionable taxonomy maps that action to null. NONE/UNCERTAIN are not executable procedure steps. The semantic action-object mapping is the shared allowlist for procedure loading and fusion, not an LLM-generated sequence.

The parser rejects missing/unknown/duplicate fields, duplicate IDs/numbers, nonconsecutive sections, inconsistent action/object pairs, empty instructions/warnings, unknown actions and invalid integers. IDs use lowercase letters/digits/underscores; confirmation_frames is 1..120 and timeout_ms is 1..86400000. Definitions are bounded to 64 steps/64 KiB; instruction/warning strings are bounded to 240 characters. UTF-8 text, including Unicode instructions, is supported. Arbitrary Markdown prose, multiline fields, tables and code fences are intentionally outside this strict format. Invalid definitions fail before opening the input or initializing YOLO.

### Fast action evidence and limitations

Fast rules are **opt-in demo calibration**, supplied using `--fast-config`; there are no default home ROIs. Edit `examples/demo_fast_rules.yaml` for the actual fixed camera/rack. ROI coordinates are normalized **original-source** x1,y1,x2,y2, not prepared-image pixels. Do not use its illustrative coordinates without calibration.

Under the demo assumption that an operator moves these tracked experiment boxes between known home regions and working space:

- Persistent visible track crossing home -> outside produces a PICK candidate.
- The same visible track returning outside -> home produces a PLACE candidate.
- MANIPULATE requires a separate `work_regions` ROI for that object, at least `work_dwell_frames` consecutive observations there (default 3), and displacement of at least `displacement_threshold` measured from the work-zone entry anchor. Ordinary carrying outside home is not manipulation evidence. Leaving work, a missing frame or changed identity clears dwell evidence. Step confirmation still applies after the candidate is produced.
- Candidates require the matched procedure step's number of consecutive detector frames. Missing/gapped frames, boundary jitter and uncertain observations break the streak. A confirmed candidate is latched until a different action or sufficient neutral evidence prevents per-frame repeats.

No raw vertical direction or object disappearance determines PICK/PLACE. Untracked objects, identity changes, duplicate same-class detections and simultaneous candidates are uncertain. Optional `reference_object` rejects missing/moving rack reference evidence; after reference movement, reset/recalibrate the setup. Without a configured home region, fast PICK/PLACE/MANIPULATE remain UNCERTAIN.

These rules detect **supported demo state transitions**, not grasp/release physics. Object motion, occlusion, camera motion and incorrect ROI calibration can invalidate the interpretation. Hand interaction evidence is not supplied by Module 03 to this assistant. Fast physical PICK versus PLACE reliability is not established. A rotated setup requires corresponding ROI calibration; rotation-based ground demonstrations only approximate orientation-agnostic behavior and do not prove real microgravity performance.

### Deterministic sequence and Qwen fusion

A correct confirmed action completes only the current step and suggests the next instruction. Observing a later unfinished step on the same object emits SKIPPED_STEP, identifying intervening steps; observing a later step on a different object emits WRONG_ORDER. Neither advances state. An already-completed action emits REPEATED_ACTION without error speech. The assistant's explicit action relevance filter logs `NON_PROCEDURAL_ACTION` for a taxonomy-valid action on a procedure object when that action/object pair appears nowhere in the loaded procedure. Such incidental actions do not reach confirmation/validation, change state, or generate voice. Thus carrying yellow never requires MANIPULATE_YELLOW in a pick/place-only procedure; another procedure can still require it. Unknown actions, mismatched action/object pairs or unrelated objects remain unexpected when confirmed. NONE/UNCERTAIN never advance state. An explicit timeout emits STEP_TIMEOUT once per expected step, using elapsed high-resolution monotonic host time since that step began (not source-video playback timestamps).

Fast confirmations are accepted immediately without waiting for Qwen. Qwen remains asynchronous and event-triggered, and does not parse Markdown, order steps or control speech. When fast evidence is uncertain, semantic refinement requires `confirmation_frames` distinct chronological READY semantic event results; replaying the same result on successive display frames does not count. This conservative semantic path can be slow. Stale results older than the latest committed action or more than 10 source seconds old are ignored. A later disagreement with a fast result is logged and does not retract state or generate retroactive warnings. No calibrated confidence is claimed.

Upstream reset clears the assistant's classifier/confirmation/fusion, procedure progression, pending voice alerts, cooldown and displayed latency. Active voice playback is canceled and generation tokens prevent stale audio callbacks publishing latency. Prepared/source pixels and downstream ObjectFrame remain clean.

### Local Piper setup and voice policy

The optional backend uses the maintained [Piper Python API](https://github.com/OHF-Voice/piper1-gpl/blob/main/docs/API_PYTHON.md), with local ONNX/config assets and bundled English eSpeak phonemization. Other language frontends are rejected in this initial offline backend because some can fetch auxiliary models. Audio uses the installed local sounddevice/PortAudio interface. Install optional dependencies during setup:

```powershell
.\.venv\Scripts\python.exe -m pip install -r 02_yolo/requirements-voice.txt
# Explicit, optional setup download only; this command is NEVER run by Module 02:
.\.venv\Scripts\python.exe -m piper.download_voices en_US-lessac-medium
```

Keep both `en_US-lessac-medium.onnx` and `en_US-lessac-medium.onnx.json` locally. Then:

```powershell
.\.venv\Scripts\python.exe -m 02_yolo --source demo.mp4 --procedure 02_yolo/examples/red_yellow_procedure.md --fast-config 02_yolo/examples/demo_fast_rules.yaml --piper-model C:/orbita-assets/en_US-lessac-medium.onnx --events-jsonl procedure-events.jsonl
.\.venv\Scripts\python.exe -m 02_yolo --source 0 --procedure 02_yolo/examples/red_yellow_procedure.md --no-voice
```

`--voice`/`--no-voice` controls the procedure voice branch. Voice is enabled by default in procedure mode; backend selection is described in the next section. If no local backend can speak, voice becomes VOICE_UNAVAILABLE; detector, tracking, validator, video and logs continue. VOICE_ERROR isolates synthesis/playback failures. There is no runtime installation, model download or daemon spawning. Dependency/model setup can use the internet explicitly; normal operation needs only local assets and optional localhost Ollama.

One voice worker loads the model once and pre-synthesizes deduplicated procedure warnings, next-step prompts and optional success/completion phrases. Warm-up produces no unsolicited test speech. Wait for VOICE READY before beginning a timed demo. PCM is held in a procedure-scoped cache (default maximum 512 entries/64 MiB; individual clips <=20 seconds). No temporary audio files are created. Reset retains the warmed voice/cache; close releases them. Critical clips remain cached; uncached dynamic messages are synthesized on the worker and logged separately.

Errors have priority 1, timeouts 2, next prompts 3 and optional success acknowledgements 4. Errors supersede queued lower-priority information and can cancel an active lower-priority prompt. The queue is bounded to eight pending alerts; duplicates coalesce, and a full queue rejects a new alert unless it can displace lower-priority speech. Keyed cooldown defaults to 2500 ms (`--alert-cooldown-ms`). Policy defaults: errors ON, next-step prompts ON, success OFF. Use `--no-speak-next-step` or `--speak-success` as needed. Audio-device selection is available via `--audio-device INDEX`.

### Multi-backend offline voice (cached WAV / SAPI5 / Piper)

Voice is a side effect of validated procedure events. `AlertManager` talks to one TTS boundary (`load`/`synthesize`/`close`); `alerts.voice_router.VoiceRouter` puts three local backends behind it. The validator, fast classifier, YOLO and Qwen never see which backend spoke, and every backend's PCM goes through the same bounded worker, priority/preemption, cooldown and PortAudio onset timing.

```text
ProcedureValidator -> AlertManager -> VoiceRouter (startup probe, fixed order)
                                       |-- cached_wav : verified pre-generated WAV, playback only
                                       |-- sapi5      : installed Windows voice -> in-memory PCM
                                       '-- piper      : local Piper ONNX voice (runtime synthesis)
```

| Backend | What runs at alert time | Platform | Network |
|---|---|---|---|
| `cached_wav` | WAV lookup only (no synthesis) | any | none |
| `sapi5` | Windows SAPI5 renders to an `SpMemoryStream` (text spoken literally, not as SAPI XML); leading/trailing silence trimmed | Windows; needs pure-Python `comtypes` | none (OS voices David/Zira verified) |
| `piper` | Piper ONNX synthesis; native eSpeak phonemizer | Linux, or Windows where the policy admits `espeakbridge.pyd` | none |

`--voice-backend auto` (default) probes each configured backend **once** at startup; a backend that fails its probe is never retried per alert. Order is deterministic:

- Windows: `cached_wav` -> `sapi5` -> `piper`.
- Other platforms: `piper` -> `cached_wav` -> `sapi5`.

Each message uses the first ready backend that can voice it. A message missing from the cache (for example a next-step prompt) falls to SAPI5 for that message only. All fixed procedure messages are still pre-rendered into memory during warm-up, critical warnings first, so a critical warning is a memory lookup whichever backend produced it. Messages no backend can voice are skipped individually and logged (`voice_preload_miss`).

An explicit `--voice-backend cached_wav|sapi5|piper` never falls back. If it is unavailable, voice reports VOICE_UNAVAILABLE with `requested voice backend ... unavailable` and the reason. A Piper eSpeak bridge refused by Windows Application Control is reported as `BLOCKED_POLICY` (not retried).

Startup status, the HUD line (`Fixed: CACHED_WAV 21 | Dynamic: SAPI5 | PIPER: BLOCKED_POLICY`) and `--jsonl` `voice_backends` report the probe result per backend, the dynamic backend, and how many fixed messages each backend produced. Every `audio_playback_started` event records `voice_backend`. Piper is never shown as ready unless its phonemizer probe passed.

**Pre-generated cache.** Build the cache wherever a backend works, typically Piper on an approved Linux machine, then copy the folder to the demo PC:

```powershell
python 02_yolo/tools/build_voice_cache.py --procedure 02_yolo/examples/red_yellow_procedure.md --backend piper --piper-model <voice>.onnx --output voice_cache/
python -m 02_yolo --source 0 --procedure 02_yolo/examples/red_yellow_procedure.md --fast-config 02_yolo/examples/demo_fast_rules.yaml --voice-cache voice_cache/manifest.json
```

`manifest.json` (`orbita-voice-cache/1`) records the experiment name and the generator backend/voice (and Piper voice SHA-256). Entries are keyed by `step_id/KIND` (for example `manipulate_red/SKIPPED_STEP`, `_procedure/COMPLETED`), each with the exact text, a WAV file name and the file's SHA-256. File names are not the contract.

At startup every entry is verified:
- the key belongs to the loaded procedure;
- the text equals what that procedure would speak now (stale wording is rejected);
- the file is a plain local `.wav` name;
- the SHA-256 matches;
- the audio is audible PCM16, 8–96 kHz, at most 20 s.

A bad or missing entry is rejected individually and its message falls back. A manifest for another experiment, with duplicate keys or a wrong format, is rejected as a whole. `--backend sapi5` is also supported by the builder, and its manifest says so. The cache folder is a deployment asset: it is not committed in this repository.

Honest scope: on Windows, critical warnings can use **Piper-generated audio** from the cache. Runtime Piper synthesis on Windows depends on Smart App Control admitting the unsigned `espeakbridge.pyd`; the startup probe decides this per run, so the same command works when it is blocked.

Setup: `comtypes` (pure Python, no native binaries) is in `requirements-voice.txt` for Windows. `--sapi-voice` selects an installed SAPI5 voice by name substring.

### HUD, logs and warning latency

Procedure mode appends a fixed 196-pixel display panel below the source-sized annotated frame. The source area and box coordinates are unchanged, and video dimensions remain stable across status updates. It shows step/expected/observed/next instruction, VOICE status and a latency value only after an audio-start callback. `--jsonl` retains per-frame detector/semantic records and adds procedure/voice side outputs only in procedure mode. `--events-jsonl` records bounded-state assistant events and voice instrumentation; in-memory event history is capped at 128 records.

Warning latency is T1 minus T0: T0 is `time.perf_counter()` **after multi-frame violation confirmation**, before validation/queueing; T1 is first non-silent audio output onset. Confirmation, scheduling and playback share the injectable `alerts.timing.host_time` basis. Records include violation_confirmed_timestamp, alert_queued_timestamp, audio_playback_start_timestamp and warning_start_latency_ms. Playback takes the relative [PortAudio outputBufferDacTime](https://python-sounddevice.readthedocs.io/en/latest/api/streams.html) minus PortAudio currentTime, adds it to host perf_counter in the callback, and adjusts for leading PCM silence. Absolute device and host timestamps are never subtracted. This is a device-clock onset **estimate**, not acoustic microphone/speaker verification. Queue insertion alone is never reported as audio start.

Preferred design target is <=1000 ms; maximum target <=1500 ms. It applies only to calibrated, supported fast-path violations, and includes queue/preemption/cache/device delay. `--fast-config` with home ROIs and work ROIs for required manipulation actions is needed for that path. Startup prints/logs per-action YES/NO coverage; missing/partial calibration warns that Qwen-dependent warnings may exceed 1.5 s. Home-only legacy files still support PICK/PLACE but cannot confirm MANIPULATE. ROI coordinates must be normalized, have usable interiors after the boundary margin, and an object's home/work interiors must not overlap. Object names must match the action configuration. Calibration coverage describes structural support, not measured action accuracy.

Measured on the development machine (Windows 11, Realtek speakers via MME, Smart App Control ON) on 2026-10-05. These are injected confirmed violations through the real validator and alert manager, with real audio output, using the PortAudio device-clock onset estimate. They are not acoustically verified.

| Path (warning-start latency) | n | min | median | p95 | max |
|---|---|---|---|---|---|
| Cached Piper WAV, warm | 10 | 344 ms | 345 ms | 355 ms | 357 ms |
| Cached Piper WAV, cold (fresh assistant, warning during warm-up) | 3 | 351 ms | 360 ms | 420 ms | 427 ms |
| SAPI5 dynamic (synthesized at alert time) | 10 | 319 ms | 324 ms | 330 ms | 333 ms |
| Runtime Piper, warm (pre-rendered) | 10 | 348 ms | 350 ms | 355 ms | 355 ms |
| Runtime Piper, dynamic | 3 | 423 ms | 435 ms | 440 ms | 441 ms |
| Runtime Piper, cold (model load + warm-up first) | 3 | 3022 ms | 3047 ms | 3219 ms | 3238 ms |

The cold runtime-Piper row misses the 1.5 s target. That is why critical warnings should use the cached WAV path and timed demos should wait for VOICE READY.

Smart App Control blocked Piper's unsigned `espeakbridge.pyd` earlier the same day (Code Integrity 3033/3077, `VerifiedAndReputableDesktop`). Later, the identical file (same SHA-256) loaded with SAC still enforcing, consistent with a changed cloud reputation verdict; no security setting was changed. That verdict is outside the project's control and may differ on another PC; the startup probe reports `BLOCKED_POLICY` and `auto` continues with the cache/SAPI5. See [PIPER_POLICY_OWNER_REPORT.md](PIPER_POLICY_OWNER_REPORT.md) and [REAL_PIPER_RUNTIME_REPORT.md](REAL_PIPER_RUNTIME_REPORT.md) for the earlier blocked-state evidence. Unit-test/mock timings are not a real latency result.

```powershell
# Cached WAV / SAPI5 variants (same tool; results record voice_backend):
.\.venv\Scripts\python.exe 02_yolo/tools/benchmark_alert_latency.py --voice-backend cached_wav --voice-cache voice_cache/manifest.json --samples 10 --cold-samples 3 --dynamic-samples 0
.\.venv\Scripts\python.exe 02_yolo/tools/benchmark_alert_latency.py --voice-backend sapi5 --samples 1 --cold-samples 0 --dynamic-samples 10
# Speak one short readiness phrase, only when explicitly invoked:
.\.venv\Scripts\python.exe 02_yolo/tools/benchmark_alert_latency.py --piper-model C:/orbita-assets/en_US-lessac-medium.onnx --smoke-only
# Inject actions through the validator and measure real Piper/device onset:
.\.venv\Scripts\python.exe 02_yolo/tools/benchmark_alert_latency.py --piper-model C:/orbita-assets/en_US-lessac-medium.onnx --samples 10 --cold-samples 3 --dynamic-samples 3 --jsonl C:/orbita-scratch/latency.jsonl
```

The benchmark reports separate cold, warm cached and dynamic uncached counts/minimum/median/p95/maximum. Each warning starts with a confirmed injected action, runs through the actual validator and alert manager, and uses Piper-produced PCM. Cold samples include voice/cache warm-up; dynamic samples deliberately clear cached PCM to exercise synthesis. It never labels these events real camera detections. Inspect/listen on the actual demo machine; acoustic verification requires external recording/measurement. Missing assets, policy blocks or devices return NOT VERIFIED with the actual failure and no fabricated timing values. Reset cancels old playback, clears its active duplicate key and accepts the same new-generation prompt while discarding stale callbacks.

This remains a hackathon prototype: not flight-certified, not safety-certified, microgravity unverified. Real operator footage, physical webcam, rotation demo and fast-action accuracy remain unverified; warning latency above is a device-clock estimate, not an acoustic measurement. Run the existing Module 02/full pytest suites, Ruff, compileall and `python -m yolo.tests.verify_types`; the type verifier includes the new procedure/alerts packages.
