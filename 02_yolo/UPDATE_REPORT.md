# MODULE 02 UPDATE RESULT

## Status

**COMPLETE** ? implementation and applicable automated verification are complete. Physical webcam/display operation, representative performance, action accuracy and real microgravity behavior remain unverified; they are not claimed as implementation results.

## Architecture

```text
FramePacket -> Module 01 (unchanged) -> PreparedFrame -> SIH adapter
                                                           |
OpenCV webcam / image / MP4 -> Standalone adapter -> InputFrame
                                                           |
                         SAME core.DetectorPipeline + Ultralytics detector
                         parsing / filtering / tracking / source restoration
                                                           |
             +---------------------------------------------+--------------------+
             |                                             |                    |
SIH shared ObjectFrame -> Module 03               source-frame renderer    event trigger
standalone DetectionFrame                        original BGR COPY       bounded JPEG buffer
                                                   annotated output            |
                                                                    one Ollama worker
                                                                            |
                                                               validated SemanticResult
                                                               (side output only)
```

The existing detector, filter, result-parser and restoration algorithms were relocated, with contract constructors injected by adapters. Existing public SIH pipeline and inference imports are compatibility facades, including shared InitializationError and logger compatibility. One implementation serves both execution modes. No model math, second NMS/letterbox step, FSM, procedure rules or voice engine was added.

## Module 01 Changes

**NONE.** Module 01 source, FramePacket, PreparedFrame, FrameProcessor, scale/color/CLAHE/reset metadata and public APIs are unchanged. Original pixels remain authoritative.

## Module 03 Changes

**NONE.** Module 03 runtime and shared ObjectFrame are unchanged. It consumes the original prepared frame and the same shared ObjectFrame, without semantic results or rendered pixels.

`git diff --exit-code -- 01_perception_core 03_optimization shared perception optimization integration` completed successfully with no output. New standalone output is named DetectionFrame, avoiding redefinition of the shared ObjectFrame schema; the repository contract-ownership test passes.

## HAR.zip Analysis

ZIP member names, source text and checkpoint pickle opcodes were inspected safely before implementation. No torch.load/unpickling was used to inspect metadata. Only the selected, size/digest-checked best.pt was extracted; both weights were not duplicated into runtime assets.

| File | Purpose | Reused? | Destination |
|---|---|---|---|
| HAR/ | Archive directory | No | Reference archive |
| HAR/main.py | 8,013-byte webcam YOLO("best.pt") loop, confidence 0.45, class-keyed y-center/aspect smoothing, debounce, action rules, ExperimentSequence, HUD and pyttsx3 voice | ADAPT selected concepts | Bounded event buffering, direction-independent trigger, OpenCV capture and renderer; no blind port |
| HAR/best.pt | 6,249,770-byte YOLOv8n DetectionModel; checkpoint Ultralytics 8.4.162; 0 lid, 1 main_box, 2 red_box, 3 yellow_box | REUSE | Local Git-ignored 02_yolo/models/best.pt and matching HAR class/profile YAML |
| HAR/weights.pt | 5,423,109-byte YOLO26n / yolo26n.yaml DetectionModel; checkpoint 8.4.55; 0 HAR, 1 Lid, 2 main_box, 3 red_box, 4 yellow_box | DISCARD from active configuration | Remains in archive, unused by main.py, not extracted/loaded |

A/B/C/D classification: local detector and display concepts **ADAPT**; best.pt **REUSE**; sequence validation and speech **MOVE ELSEWHERE** in architectural ownership only (no files/code actually moved); vertical PICK/table-return/aspect action authority **DISCARD**. ObjectTracker in main.py is smoothing keyed by class, not persistent multi-object ID tracking. Existing ByteTrack implementation is retained.

Existing `procedure/fsm.py`, `step_validator.py` and `procedures/demo_experiment.yaml` were inspected. They are downstream ActivityEvent procedure scaffolds with placeholder activity/object labels; they do not define a competing validated Module 02 action vocabulary. Semantic defaults preserve the prototype's six action labels plus NONE/UNCERTAIN, with configurable action-object mappings. No procedure code changed.

Digests:

- best.pt: b9ab5c71a5c4e0ed151d6e8001983e5e7d5a5995a73cc419d580da304f1c687d
- weights.pt: 8884dd82cff5c497f59ae09a8076dc8d26dd12fbce59fa2dfbaafe40235c425a

The audit is reproducible with tools/inspect_har.py; tools/extract_har_model.py performs explicit local model setup. The supplied archive was already untracked before this task and remains unchanged. The checkpoint metadata carries Ultralytics AGPL licensing.

## YOLO

- **Weights used:** local 02_yolo/models/best.pt, configurable; existing project profile preserved separately.
- **Classes:** lid, main_box, red_box, yellow_box in IDs 0?3; exact local model/map agreement enforced.
- **Tracking:** local ByteTrack, configurable; no ReID/appearance download. Real backend ID 1 persisted for four repeated detected frames. Unavailable IDs remain null with notices.
- **Input modes:** SIH PreparedFrame, standalone webcam index, local video and local image.
- **Offline:** YOLO_OFFLINE=true and YOLO_AUTOINSTALL=false; installed local assets only. CPU fallback/reset rules and reviewed geometry remain intact.

## Qwen

- **Enabled:** opt-in, disabled by default; --vlm / --no-vlm or SemanticConfig / semantic YAML.
- **Model:** qwen3-vl:2b-instruct.
- **Host:** http://localhost:11434; loopback-only HTTP, no proxies/redirects/cloud aliases.
- **Trigger:** appearance/identity changes or center displacement / image diagonal; 0.04 displacement threshold, 3-second cooldown. Optional interval_s; no per-frame requests.
- **Buffer:** default capacity 8; every second detector frame; at most 4 chronological keyframes; 640-pixel maximum side, JPEG <=1 MiB each. Capacity configurable/validated 2?64.
- **Worker:** one pending/in-flight event maximum; busy submissions dropped, no frame backlog; 30-second per-request timeout by default.
- **Context:** explicit configurable 16,384 tokens. The initial real request exceeded the local default 4,096-token context; the corrected configuration passed the local smoke.
- **Structured output:** exact JSON action/object schema, duplicate/extra-field rejection, action allowlist and matching object validation; frozen SemanticResult includes event/sample frame/timestamp, no numeric VLM probability.
- **Fallback:** missing/stopped Ollama, missing model, timeout, HTTP/API error and invalid output yield independent semantic failure status / UNCERTAIN; YOLO continues.
- **Reset:** buffer/trigger/pending/latest clear; generation tokens discard in-flight stale responses. A request already executing may finish/time out but cannot publish after reset/close.
- **Real smoke:** installed local model reachable, four chronological synthetic images accepted, parser returned READY with candidate PLACE_RED for sampled frame 3/event 1. This is transport/schema execution evidence only, not action-accuracy evidence. No model was downloaded.

Ollama wire behavior was checked against its official [chat API](https://docs.ollama.com/api/chat), [model listing](https://docs.ollama.com/api/tags) and [structured-output documentation](https://docs.ollama.com/capabilities/structured-outputs).

## Visualization

- **Input frame source:** prepared.source / original Module 01 source frame in SIH; original OpenCV input in standalone.
- **BBox coordinates:** original absolute source pixels; dimensions/frame/timestamp/source/session checked. Render-original-then-resize is the documented smaller-display approach.
- **Mutation:** none; overlays draw on a detached BGR copy, with RGB/gray source conversion when necessary.
- **Display:** OpenCV live display, annotated image and MP4 output, console JSON and optional JSONL. Integrated renderer is an explicit side branch.
- **Overlays:** class, YOLO score, box, available ID, YOLO/VLM/tracking status, frame ID and dated last semantic event.
- **Verified artifacts:** .verification/runtime/annotated.png, annotated.mp4 (4 decoded frames), integrated.mp4 (4 decoded frames from the real Module 01/02/03 path), integrated.png, tracked.png and JSONL records. tracked.png was visually inspected and showed red_box, ID 1, correct box and status HUD. Runtime artifacts are Git-ignored.

## Standalone Mode

- **Webcam:** structurally verified with mocked OpenCV capture/cleanup. Physical camera not exercised.
- **Video:** real local YOLO inference and four-frame annotated MP4 encode/decode verified.
- **Image:** real local YOLO inference, saved annotated image and console/JSONL verified.
- **Module 01 dependency:** NONE on --source / standalone.py path.
- **Module 03 dependency:** NONE.
- **Isolation:** the complete module with best.pt was copied outside the repository to C:/Users/lalit/AppData/Local/Temp/orbita-module02-d4lorvr2/module02. It performed real inference and image output with shared/perception/optimization/integration/procedure/FSM/GUI/alerts imports forbidden and sockets/DNS blocked.

Run from repository: `python -m yolo --source 0`.
Run copied directory: `python standalone.py --source 0`.

## Pipeline Mode

Verified the actual unchanged path:

```text
Module 01 FrameProcessor -> shared PreparedFrame
-> YoloPipeline/SIH adapter -> shared ObjectFrame
-> actual OptimizationPipeline (Module 03)
```

Existing adapter tests verify RGB preparation, fractional resize scales, metadata and source-coordinate restoration. The new integrated-render test verifies Module 03 consumption alongside nonmutating source-sized overlays. Real-weight smoke also passed this path with hand tracking disabled to avoid unrelated optional assets. No Module 03 code was edited and semantic output is not forwarded to it.

## Files Added

- `02_yolo/adapters/__init__.py`
- `02_yolo/adapters/sih.py`
- `02_yolo/adapters/standalone.py`
- `02_yolo/config/har_classes.yaml`
- `02_yolo/config/semantic.yaml`
- `02_yolo/config/standalone.yaml`
- `02_yolo/config/tracker.yaml`
- `02_yolo/core/__init__.py`
- `02_yolo/core/config.py`
- `02_yolo/core/contracts.py`
- `02_yolo/core/detector.py`
- `02_yolo/core/pipeline.py`
- `02_yolo/core/postprocess.py`
- `02_yolo/inputs/__init__.py`
- `02_yolo/inputs/opencv_source.py`
- `02_yolo/requirements.txt`
- `02_yolo/semantic/__init__.py`
- `02_yolo/semantic/contracts.py`
- `02_yolo/semantic/event_trigger.py`
- `02_yolo/semantic/qwen_verifier.py`
- `02_yolo/semantic/temporal_buffer.py`
- `02_yolo/semantic/worker.py`
- `02_yolo/standalone.py`
- `02_yolo/standalone_cli.py`
- `02_yolo/tests/test_extensions.py`
- `02_yolo/tools/extract_har_model.py`
- `02_yolo/tools/inspect_har.py`
- `02_yolo/tools/smoke_semantic.py`
- `02_yolo/tools/verify_runtime.py`
- `02_yolo/visualization/__init__.py`
- `02_yolo/visualization/renderer.py`
- `02_yolo/UPDATE_REPORT.md`

Local asset extracted: `02_yolo/models/best.pt` (Git-ignored, not a newly authored checkpoint). HAR.zip is a pre-existing user-supplied untracked input, not an authored file. Verification temporary/cached files are excluded from the source file list.

## Files Changed

- `02_yolo/README.md`
- `02_yolo/__main__.py`
- `02_yolo/cli.py`
- `02_yolo/inference/detector.py`
- `02_yolo/inference/postprocess.py`
- `02_yolo/input_validation.py`
- `02_yolo/models/README.md`
- `02_yolo/pipeline.py`

## Tests

Existing test files were not modified. `tests/test_extensions.py` adds **59 parametrized cases across 27 test functions**:

- `test_standalone_adapter_same_core`
- `test_standalone_adapter_rejects_bad_input`
- `test_sih_adapter_preserves_metadata_scale_and_clean_image`
- `test_integrated_renderer_and_module03`
- `test_renderer_empty_and_wrong_space`
- `test_renderer_stale_event_is_identified`
- `test_temporal_buffer_bounded_ordered_detached_reset`
- `test_temporal_sampling`
- `test_event_trigger_has_no_gravity_direction`
- `test_appearance_and_manual_interval_trigger`
- `test_qwen_parser`
- `test_no_remote_hosts`
- `test_semantic_config_validation`
- `test_qwen_payload_schema_context_and_chronology`
- `test_ollama_availability`
- `test_vlm_failure_preserves_yolo_and_renderer`
- `test_worker_bounded_nonblocking_and_reset_discards_late_reply`
- `test_pipeline_upstream_reset_clears_semantics_not_weights`
- `test_disabled_semantics_never_contacts_ollama`
- `test_standalone_image_and_video_outputs`
- `test_webcam_structure_and_cleanup`
- `test_standalone_input_errors`
- `test_copy_outside_repo_isolation`
- `test_semantic_yaml_config`
- `test_qwen_inference_failure_is_structured`
- `test_standalone_pipeline_rejects_wrong_contract`
- `test_invalid_reset_frame_clears_semantics`

## Verification Commands

The following commands were actually executed from the repository root:

```powershell
.\.venv\Scripts\python.exe -m pytest 02_yolo/tests tests/test_yolo_to_optimization.py -q -p no:cacheprovider
.\.venv\Scripts\python.exe 02_yolo/tools/inspect_har.py > 02_yolo/.verification/har-static-audit.txt
.\.venv\Scripts\python.exe 02_yolo/tools/extract_har_model.py
ollama list
.\.venv\Scripts\python.exe 02_yolo/tools/smoke_semantic.py
.\.venv\Scripts\python.exe 02_yolo/tools/verify_runtime.py
.\.venv\Scripts\python.exe -m pytest 02_yolo/tests -q -p no:cacheprovider
.\.venv\Scripts\python.exe -m pytest -q -p no:cacheprovider
.\.venv\Scripts\python.exe -m yolo --help
.\.venv\Scripts\python.exe -m compileall -q 02_yolo/core 02_yolo/adapters 02_yolo/semantic 02_yolo/visualization 02_yolo/inputs 02_yolo/tools
.\.venv\Scripts\python.exe -m ruff check 02_yolo/core 02_yolo/adapters 02_yolo/semantic 02_yolo/visualization 02_yolo/inputs 02_yolo/standalone_cli.py 02_yolo/pipeline.py 02_yolo/inference/detector.py 02_yolo/inference/postprocess.py 02_yolo/standalone.py 02_yolo/tests/test_extensions.py 02_yolo/tools --output-format concise
git diff --exit-code -- 01_perception_core 03_optimization shared perception optimization integration
git diff --check
```

Dependency setup also executed (network escalation approved after the sandbox download failed):

```powershell
uv pip install --python .venv/Scripts/python.exe --cache-dir 02_yolo/.verification/uv-cache ultralytics 'lap>=0.5.12'
```

Runtime smoke environment: Python 3.11, Ultralytics 8.4.173, Torch 2.14.1, lap 0.5.13 and OpenCV 5.0.0.93 in this repository's venv. Dependencies were installed during setup; they are not installed automatically at runtime. Existing tests still pass with these installed backends.

## Results

| Check | Actual result |
|---|---|
| Baseline before edits | 117 passed, 4 skipped |
| Final Module 02 suite | 176 passed |
| Final whole repository suite | 330 passed, 99 skipped |
| New regression cases | 59 passed |
| Lint, targeted changed/new implementation and test/tool files | All checks passed |
| Compilation | Passed |
| Frozen modules/contracts/integration diff | No changes |
| Diff whitespace check | Passed |
| Local Ollama availability/model | READY; model already installed |
| Optional four-image real VLM smoke | READY, schema-valid semantic candidate |
| Real local YOLO image/video output | Passed |
| Real backend tracking | ID 1 persisted across four repeated detected frames |
| Actual Module 01 -> Module 02 -> Module 03 + renderer | Passed, including 4-frame integrated annotated MP4 encode/decode |
| Copied standalone outside repository | Passed with real weights and forbidden SIH imports |
| Offline behavior | Socket/DNS access blocked during detector, integration and copied-package verification; localhost-only Ollama smoke separate |

The 99 skipped tests are existing repository scaffolds, not regressions concealed by changing tests. Interim regressions were repaired in production compatibility facades: exception/logger compatibility, historical InitializationError export and internal result naming. Final tests are clean. The real VLM context error was fixed through an explicit configuration field.

## Remaining Limitations

- Physical webcam capture and visible GUI windows were not exercised. Camera structure/resource cleanup is mocked; real image/video inference and saved output are verified.
- Action/detection accuracy, calibrated VLM confidence, representative FPS/latency and GPU performance: **Not measured**. Per-frame timing fields remain available but are not presented as benchmarks.
- Synthetic input and repeat-frame tracking do not establish tracking quality on real astronaut/experiment footage.
- A 2B VLM can misclassify actions; the synthetic smoke's PLACE_RED label is only a semantic candidate. It is not connected to the FSM or Module 03.
- Single images lack chronological interaction evidence; VLM usually stays WAITING. Short clips may finish before a queued event completes, which is discarded on close.
- Busy semantic events are dropped deliberately. Camera motion can trigger displacement, and large context/image settings increase resource use. In-flight requests cannot be killed safely; generations prevent stale publication.
- Existing project detector profile remains unchanged. Choose the HAR profile explicitly for these four-class weights. Weights.pt metadata was inspected but that alternative checkpoint was not loaded/inference-tested.
- OpenCV cannot reliably distinguish mid-video decode failure from end of file.
- The device was not physically disconnected from the internet; offline operation was verified by rejecting socket/DNS access. Localhost Ollama was separately verified and does not require cloud access.
- **Rotation-based ground demonstrations are only approximations of orientation-agnostic behavior and do not prove real microgravity performance.** This hackathon prototype is not flight certified, space qualified, microgravity validated, ISRO validated or safety certified.

The module is ready for independent implementation review. See README.md for actual CLI/configuration/setup commands and ownership boundaries.
