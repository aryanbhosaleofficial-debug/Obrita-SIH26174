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
