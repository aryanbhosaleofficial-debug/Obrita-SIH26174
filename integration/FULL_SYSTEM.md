# Final full-system runtime — SIH26174

This is an offline hackathon prototype for BAS experiment assistance. It is not
flight-certified spacecraft software. No real BAS environment, astronaut study,
ISRO validation or scientific procedure safety certification is claimed.

## Authoritative application and source state

Launch `python scripts/run_full_pipeline.py`. `main.py` delegates to that runner.
`integration.full_cli` configures dependencies; `FullSystemRuntime` owns the one
frame loop. Module-specific commands (`run_fusion.py`, Module 06's runner, the
standalone GUI demo) remain diagnostic tools, not competing full applications.
The old positional procedure-demo command and no-argument `main.py` remain
semantic-only compatibility aliases; they are not full perception demonstrations.

Before integration, branch `v1` was clean at `1127317` (Procedure FSM + Recovery /
Guidance Integration). Modules 01–06, the GUI, procedure configurations, recovery
and their tests were committed. No uncommitted FSM or unrelated user changes
were present. Integration changes are left unstaged for review; no commit or
push is performed automatically. Local model assets remain outside Git as
documented below. Source files do not depend on the developer's absolute paths.

## Actual data flow and responsibilities

```text
OpenCV camera/local video source → shared FramePacket (BGR)
  → Module 01 FrameProcessor → PreparedFrame retaining original source
  → Module 02 YoloPipeline → ObjectFrame in original-source pixels
  → Module 03 OptimizationPipeline → OptimizationOutputPacket
       hand inference, temporal interactions, rack reference, spatial evidence
  → Module 04 BoundaryPipeline → BoundaryOutputPacket
  → Module 05 FusionPipeline → temporally confirmed ActivityEvent

Same PreparedFrame + Module 03 rack reference
  → Module 06 TrackingIntegration/PoseHandTracker → PoseFrame

Frame identity assertions across both branches
  → ActivityAdapter (native labels or explicit configuration mapping)
  → ProcedureFSM → recovery policy → GuidanceDecision
  → existing AlertManager → offline TTS / playback
  → SessionLog wrapping existing EventLog → timestamped JSONL
  → existing PipelineBridge → Qt console (worker thread handoff)
  → annotated BGR frame → bounded AsyncRecorder / optional LocalStream
```

Module 06 is a synchronized branch after the 01–05 milestone, not another HAR
classifier. Its observations and rack features reach display/diagnostics; the
FSM receives only shared ActivityEvent packets. HAR belongs to Module 05.
Module 03 and Module 06 still run separate hand inference in real mode. This
known performance issue is preserved rather than refactoring frozen owners.

Frame ID, timestamp, source and session are checked before FSM dispatch. Module
04 has no source/session fields; it is bound through its paired frame/time and
the retained source. Both Module 06 and the application verify paired inputs.
Primary landmarks and boxes remain in original-source pixels. Anatomical hand
labels already include mirror correction; downstream consumers do not swap them.

The source supplies BGR uint8 images. Module 01 owns preparation. YOLO receives
its existing BGR API input; each MediaPipe owner performs its own required RGB
conversion. No orchestrator RGB/BGR round trip is added. Annotation operates on
a source-image copy. Rack axes come from Module 03's physical reference order;
image vertical direction has no gravity meaning.

## Setup and local assets

Verified environment: Windows, PowerShell, Python 3.14.7. The observed direct
package versions are recorded in `requirements-full-system.txt`. It is not a
complete transitive lock or a CUDA distribution selection. Dependency setup may
use the internet; normal execution must use installed packages and local assets.

```powershell
python -m venv .venv
& .\.venv\Scripts\python.exe -m pip install -r requirements-full-system.txt
& .\.venv\Scripts\python.exe scripts/run_full_pipeline.py --synthetic --no-gui
```

| Asset | Default / requirement | Verified here |
|---|---|---|
| Experiment YOLO | `02_yolo/models/experiment_objects.pt`; override `--model` | Missing; real YOLO not verified |
| YOLO class map | `configs/classes.yaml`; override `--classes` | Default IDs are placeholders; supply trained-model mapping |
| Module 03/06 hands | `models/hand_landmarker.task`; override `--hand-model` | Local model available; real tests pass |
| Module 06 body | `06_pose_tracking/models/pose_landmarker_lite.task`; override `--pose-model` | Local model available; real tests pass |
| Windows voice | Installed SAPI5 voice + comtypes + sounddevice | Microsoft David produced PCM and device playback starts |
| Piper voice | Local `.onnx` and matching voice config + optional piper-tts | Not part of the verified voice path |

Do not rename generic COCO classes to experiment objects. The class map must
match the actual trained model. Existing YOLO code validates class identity,
local weights, tracker configuration and offline library settings, and loads
the model once. Missing weights are reported before camera acquisition.
Available MediaPipe files are ignored by Git; copy them into the documented
locations when reproducing from a clone. See owner model READMEs for setup.

## Commands

All commands below are PowerShell-compatible single lines. Defaults are resolved
relative to the runtime/owner configuration files; CLI paths are relative to the
invoking directory. Absolute paths and paths containing spaces are supported.

Fast model/hardware-free logical demo:

```powershell
python scripts/run_full_pipeline.py --synthetic --no-gui --record
python scripts/run_full_pipeline.py --synthetic --scenario wrong-order --no-gui
python scripts/run_full_pipeline.py --synthetic --scenario skip --no-gui
python scripts/run_full_pipeline.py --synthetic --scenario recovery --no-gui --record
```

Paced full GUI/voice/recording recovery demonstration:

```powershell
python scripts/run_full_pipeline.py --synthetic --scenario recovery --gui --voice --voice-backend sapi5 --action-interval 90 --max-frames 600 --record
```

Use `correct`, `wrong-order`, `skip`, `repeated`, or `recovery` scenarios. Actions
are selected from the YAML definition; test ordering patterns are not procedure
logic. Default synthetic runs use 72 frames and one simulated action every 12
frames, so fast CI runs do not wait for speech to finish. For an audible demo,
use 90-frame action spacing and a longer run as above. GUI implies pacing; use
`--realtime` to pace headless synthetic input. EOF automatically closes the GUI.

The red/yellow scene uses generated pixels and inference fakes. Its semantic
events are explicitly simulated at the HAR-output boundary. It does not claim
that Module 05 recognized pick/place actions from those pixels. To consume the
actual Module 05 rules with only inference substituted:

```powershell
python scripts/run_full_pipeline.py --synthetic --scenario fusion --procedure procedures/fusion_touch_move.yaml --no-gui --record
```

Live camera with native Module 05 labels (requires trained local weights/map):

```powershell
python scripts/run_full_pipeline.py --source 0 --procedure procedures/fusion_touch_move.yaml --model "C:\Models\experiment_objects.pt" --classes "C:\Models\experiment_classes.yaml" --gui --voice --record
```

Local video, GUI and headless variants:

```powershell
python scripts/run_full_pipeline.py --source "data\videos\demo.mp4" --procedure procedures/fusion_touch_move.yaml --model "C:\Models\experiment_objects.pt" --classes "C:\Models\experiment_classes.yaml" --gui --voice --record
python scripts/run_full_pipeline.py --source "data\videos\demo.mp4" --procedure procedures/fusion_touch_move.yaml --model "C:\Models\experiment_objects.pt" --classes "C:\Models\experiment_classes.yaml" --no-gui --record
```

These live/video inference acceptance commands were not validated with real
YOLO here because experiment weights and a completed class map were unavailable.
Video acquisition, BGR identity and EOF were tested with injected inference fakes.

## Activity vocabulary and red/yellow proxies

Module 05 currently emits `touch_object`, `move_object`, `rotate_object`,
`release_object`, `approach_object`, and unknown observations. The red/yellow
procedure expects object-specific pick/place labels. The application rejects
an incompatible native vocabulary rather than silently waiting forever.

`ActivityAdapter` is the single mapping boundary. It preserves event ID,
frame/time, target, source/session, confidence and upstream confirmation flags.
Unmapped labels pass through. It adds the original label and mapping semantics
to audit metadata when a label is changed. No duplicate confirmation is added.

An explicitly selected inert-box demonstration proxy is provided:

```powershell
python scripts/run_full_pipeline.py --source 0 --procedure procedures/red_yellow_box.yaml --event-map configs/red_yellow_demo_proxy.yaml --model "C:\Models\red_yellow.pt" --classes "C:\Models\red_yellow_classes.yaml" --gui --voice --record
```

That map treats contact as a pick proxy and departure as a place proxy. Contact
does not prove lifting; departure does not prove placement in the target area.
This is clearly marked `demo_proxy` in metadata/GUI and is not a validated
scientific action recognizer. A real experiment needs reviewed activity rules
or a real HAR model emitting the intended semantics. Recovery never infers a
physical undo. The frozen FSM's conservative defaults remain intact.

## GUI, controls and threading

The Qt main thread owns widgets. Capture/inference runs in one application
worker; `PipelineBridge` delivers queued signals and a latest-frame image slot.
Snapshots refresh at approximately ten requests/second, with immediate meaningful
decisions. They contain procedure state/instruction/progress, observed activity,
decision/recovery, guidance, confidence, health, rack readings, logs and actual
playback status. Existing console sections display those fields.

The integrated BGR frame already contains object/body/hand overlays and physical
rack axes. `Scene.overlays_rendered` prevents the GUI painting its default demo
axes over calibrated pixels. The camera pane contains the whole image instead
of cropping rotated/portrait source frames. This is a narrow compatibility fix;
the standalone simulated GUI keeps its existing overlay behavior.

Keys: Q/ESC close; Space pauses; C resumes; R resets/starts the procedure; A aborts.
The existing voice toggle mutes/cancels voice output. Recovery requiring restart
still requires reset; resume is operator acknowledgment, not a physical undo.
Capture driver calls may block natively; worker shutdown reports a timeout if a
driver does not return. Live camera shutdown still needs hardware acceptance.

For an automated Windows GUI check:

```powershell
$env:QT_QPA_PLATFORM = 'offscreen'
python scripts/run_full_pipeline.py --synthetic --gui --gui-shot outputs/debug_frames/full-system.png
Remove-Item Env:\QT_QPA_PLATFORM
```

Remove that environment variable before a visible demonstration.

## Voice, logging, recording and streaming

Voice uses existing AlertManager/VoiceRouter, SAPI5/cached WAV/Piper and its bounded
worker. FSM guidance keys/cooldown plus AlertManager dedupe suppress repetitions.
Successful recovery cancels obsolete recovery speech before dispatching the next
instruction. Logs distinguish request, queue and actual device-clock playback
start. No speech is inferred from an enqueue. Missing TTS/device assets degrade
without stopping perception. Closing the runtime cancels pending audio and joins
the worker; rapid demos may intentionally cancel unfinished speech at EOF.

SessionLog reuses EventLog and adds UTC plus session IDs. Default unique JSONL
files live in `outputs/events/`. Records include system lifecycle, confirmed
activity, guidance, recovery transitions, playback and output errors. Bounded
in-memory history continues on file-open/write failure, reported as DEGRADED.
The frozen auxiliary logger now exposes its already-caught write error as
`last_error` and provides a locked `snapshot()` for GUI reads while the voice
worker logs. Existing write-failure behavior remains nonfatal.

`--record` uses a unique annotated `.avi`; an explicit `.avi`/`.mp4` path is also
accepted. A bounded queue separates inference from VideoWriter. Slow disk drops
recording frames without blocking the FSM. JSONL beside the video identifies
each written frame's source ID, session, frame ID and timestamp. Fixed-FPS video
playback does not imply real-time capture; consult its sidecar for source timing.
The writer is released on EOF, interruption and errors. Summary reports written
and dropped counts. Codec/device/path failures degrade the recording output.

Optional local stream:

```powershell
python scripts/run_full_pipeline.py --synthetic --gui --stream --stream-host 127.0.0.1 --stream-port 8080
```

Open `http://127.0.0.1:8080/stream` or `/frame.jpg`. Use explicit
`--stream-host 0.0.0.0` to bind the demo LAN and access it using the machine's
LAN address. Hosts must be literal IPv4 addresses. Latest-frame buffering,
four-client limit and socket timeouts keep slow/disconnected clients from
blocking inference. Port/encoding failures degrade without stopping the core.
There is no authentication; keep this optional stream on a trusted isolated LAN.
Remote client/cross-machine LAN performance was not measured here.

`--diagnostics outputs/events/frames.jsonl` opts into per-frame shared activity,
tracking, guidance, health and measured stage timing records. Normal event logs
do not write verbose raw-frame records. Core latency excludes display/output work;
observed loop FPS includes pacing, startup and shutdown and is not model FPS.

## Configuration and failures

`configs/runtime.yaml` coordinates owner configuration paths, output directories,
synthetic length, recording FPS and local stream address. Owner thresholds remain
in their existing YAML files. CLI provides source, model, class-map, procedure,
event-map, config and output overrides. Output paths are checked against each
other, source inputs, owner configs and models before output creation.

| Symptom | Action |
|---|---|
| YOLO model not found | Supply trained local weights and matching classes; use synthetic for wiring checks. |
| HAR cannot produce a procedure action | Use native procedure labels, reviewed mapping, or explicit demo proxies. |
| Missing MediaPipe model | Supply `--pose-model`/`--hand-model` local Tasks files or synthetic mode. |
| Camera/video absent or empty | Check source index/path; empty source is an explicit error. |
| PySide6 missing | Use headless mode or install GUI dependencies during setup. |
| VOICE_UNAVAILABLE/VOICE_ERROR | Check local voice/device; procedure processing continues. |
| Recording/Streaming/Logging DEGRADED | Inspect output error; core inference continues. |
| No person/hands/object | Waiting/no-detection is valid; no fabricated activities. |
| Frame/session mismatch | Run stops before mismatched semantic input can advance the FSM. |

## Orientation and offline verification

```powershell
python scripts/run_full_pipeline.py --synthetic --rotation 0 --no-gui
python scripts/run_full_pipeline.py --synthetic --rotation 90 --no-gui
python scripts/run_full_pipeline.py --synthetic --rotation 180 --no-gui
python scripts/verify_full_system_offline.py --synthetic --scenario recovery --no-gui --record
```

Rotation tests transform generated source pixels, detection/hand geometry,
landmarks and physical rack corner order together. Tests verify invariant
rack-relative coordinates, anatomical labels and FSM results. Manual reference
calibration is explicitly known in the synthetic setup; for live orientation,
Module 03's ArUco calibration requires its configured physical marker IDs.
This is a ground prototype approximation, not microgravity validation.

The offline verifier forbids Python outbound socket connection calls for that
execution. It does not disable adapters/firewalls or prove every native library
path. The full recovery GUI/SAPI5/recording demo was executed under this guard.
No cloud dependency exists in the full runner. YOLO owner code enforces local
weights, disables auto-install and rejects online Ultralytics settings. Module 06
loads local Tasks files; TTS uses local backends. No VLM/cloud client is created
by this runner. Optional streaming only serves local frames.

## Verification and SIH demo checklist

```powershell
python -m pytest -q tests/test_full_system_runtime.py tests/test_full_system_outputs.py tests/test_full_system_cli.py
python -m pytest -q
```

See `FULL_SYSTEM_VERIFICATION.md` for exact executed results and artifact paths.

### Verify a clean committed checkout

Use the same installed dependency environment, but do not copy ignored models or
runtime artifacts into the checkout. In PowerShell, from the repository root:

```powershell
$cleanCheckout = Join-Path ([System.IO.Path]::GetTempPath()) ('SIH26174 clean HEAD ' + [guid]::NewGuid().ToString('N'))
git worktree add --detach "$cleanCheckout" HEAD
Push-Location "$cleanCheckout"
try {
    python -m pytest -q
    python -c "import integration, integration.full_system, procedure; print('imports OK')"
    python scripts/run_full_pipeline.py --help
    python scripts/run_full_pipeline.py --synthetic --no-gui
    python scripts/verify_full_system_offline.py --synthetic --scenario recovery --no-gui --record
} finally {
    Pop-Location
}
```

Check each command's exit code; do not infer success from the final command alone.
Retain the worktree for review. Optional real-model tests will skip when local
assets are absent; the synthetic pipeline requires committed source/configs and
installed dependencies only. Offscreen GUI execution is covered by
`tests/test_full_system_cli.py::test_full_gui_offscreen_updates_and_worker_exits`.
Voice integration is verified by tests; manually audible hardware playback is a
separate physical-demo check. The offline guard tests Python connection calls,
not a disconnected network adapter or every native-library path.

- [ ] Disconnect internet for the physical SIH demo.
- [ ] Copy local trained YOLO weights and complete their class mapping.
- [ ] Copy local MediaPipe/voice assets and verify dependencies.
- [ ] Confirm the physical camera opens and calibrated rack markers are visible.
- [ ] Demonstrate the reviewed procedure with real recognition.
- [x] Demonstrate correct, wrong-order, skipped and recovery logic synthetically.
- [x] Verify offline voice integration, warning dedupe and worker shutdown in tests.
- [ ] Manually hear and verify voice guidance on the physical demo audio device.
- [x] Confirm JSONL logs and decodable recorded video are generated.
- [x] Verify the GUI reflects guidance/state using the real bridge.
- [x] Verify generated 0/90/180-degree orientation invariants.
- [x] Verify automated EOF/interrupt/stop cleanup and local stream shutdown.
- [ ] Verify Q/ESC/close and capture cleanup with the physical camera driver.

Known limits: missing trained YOLO/class map; red/yellow pick/place semantics are
simulated or explicit proxies; duplicate hand inference; ground data/testing;
no real BAS or microgravity environment; single source/operator and linear FSM;
no certified procedure safety; blocking native driver calls cannot be preempted
by Python. Model files and runtime media/logs are intentionally excluded from
source commits. Integration source is ready for review; real live acceptance
requires the missing assets and reviewed action semantics.
