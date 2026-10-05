# Full-system verification — 2026-10-05

## Repository baseline

Branch: `v1`. HEAD: `1127317` (Procedure FSM + Recovery / Guidance Integration),
also referenced by `origin/v1`, `origin/main` and local `main` at inspection.
Initial `git status --short` and staged diff were empty. Procedure/FSM/recovery,
Modules 01–06 and GUI source/tests were committed. Their owners were not broadly
refactored. New integration changes remain unstaged for review; no commit/push.

Python 3.14.7 on Windows/PowerShell. Observed package versions are recorded in
`requirements-full-system.txt`. No package installation or model download was
performed for this task. Local MediaPipe assets were available; experiment YOLO
weights were not. Default YOLO class-map IDs remain placeholders.

## Exact final tests

| Command | Passed | Failed | Skipped | Errors |
|---|---:|---:|---:|---:|
| Baseline `python -m pytest -q` | 1080 | 0 | 44 | 0 |
| `python -m pytest -q tests/test_full_system_runtime.py tests/test_full_system_outputs.py tests/test_full_system_cli.py GUI/tests 02_yolo/tests/test_procedure.py 02_yolo/tests/test_procedure_repair.py` | 81 | 0 | 0 | 0 |
| `python -m pytest -q 06_pose_tracking/tests/test_pose_real_models.py tests/test_local_inference_assets.py -rs` | 7 | 0 | 1 | 0 |
| Final `python -m pytest -q` | **1116** | **0** | **44** | **0** |

Final focused run: 13.05 seconds. Final full suite: 37.73 seconds. All 36 added
full-system tests pass; the repository skip count is unchanged. Intermediate
development tests exposed issues which were corrected before this final run.

Real-asset skip: `02_yolo/models/experiment_objects.pt` absent. MediaPipe tests
covered local model loading, blank-scene behavior, partial-model degradation,
positive pose sample and two-hand/mirror semantics where local fixtures existed.
They do not establish experiment-recognition accuracy or real BAS performance.

New integration coverage includes five procedure scenarios, real Module 05
rules, duplicate dispatch, frame/source/session rejection, GUI dictionaries and
offscreen Qt execution, local JPEG/MJPEG clients, streaming-port failure, real
VideoWriter decoding/metadata, logger creation/write failure, concurrent voice
logging snapshots, voice-worker lifecycle and TTS failure, interruption/stop,
rotated rack invariants, external working directories/space-containing paths,
empty source, actual local-video EOF with inference fakes, and blocked outbound
Python connections. No webcam or GPU is required by these new tests.

## Executed full-system demonstrations

Correct/wrong-order/skip/repeated/recovery scenarios all run the real 01–06 owner
APIs with inference fakes and explicitly simulated semantic HAR outputs. Correct
and recovery complete all four steps. Wrong order leaves zero steps completed;
skip leaves only step 1 completed; repeats do not advance twice.

Executed standalone orientation/error demonstrations:

```powershell
python scripts/run_full_pipeline.py --synthetic --scenario wrong-order --rotation 90 --log outputs/events/final-wrong-order.jsonl
python scripts/run_full_pipeline.py --synthetic --scenario skip --rotation 180 --log outputs/events/final-skip.jsonl
python scripts/run_full_pipeline.py --synthetic --scenario fusion --procedure procedures/fusion_touch_move.yaml --log outputs/events/final-native-fusion.jsonl
```

All exited 0. The native fusion scenario completed `touch` then `move` using the
actual Module 05 confirmed event output rather than semantic simulation.
Orientation unit tests also verify 0/90/180-degree rack-coordinate invariants and
unchanged anatomical hand labels. This is generated ground imagery plus known
manual calibration, not microgravity or real marker/camera-rotation validation.

The combined offscreen GUI/SAPI5/recovery recording demonstration also ran with
outbound Python socket calls forbidden:

```powershell
$env:QT_QPA_PLATFORM = 'offscreen'
python scripts/verify_full_system_offline.py --synthetic --scenario recovery --gui --voice --voice-backend sapi5 --action-interval 90 --max-frames 600 --record outputs/recordings/full-system-offline.avi --log outputs/events/full-system-offline.jsonl --gui-shot outputs/debug_frames/full-system-offline.png
```

Observed results:

- Exit 0; 600 processed frames; FSM COMPLETED with all four steps.
- 600 video frames written, **600 decoded**, 600 identity-sidecar records;
  zero recording drops.
- Six actual `audio_playback_started` records: initial instruction, next step,
  skip warning, recovery next step, next step and completion.
- SAPI5 backend: Microsoft David Desktop — English (United States).
- PortAudio device-clock first-nonsilent-PCM playback-start estimates were logged.
  This is device scheduling evidence, not a listener assessment of intelligibility.
- The skip warning was dispatched once in that run. Obsolete recovery speech is
  canceled when correction completes; voice worker is joined on shutdown.
- GUI screenshot generated and reviewed; procedure state/progress/logs appeared.
- No output errors; final voice lifecycle STOPPED; camera/model/output resources
  exited. Optional stream was OFF for this particular combined run.

Artifacts are in ignored output directories. Separate streaming tests fetched
and decoded JPEG and MJPEG over real loopback sockets, tested an occupied port,
and verified server shutdown. Cross-machine LAN operation was not exercised.

## Actual measurements

The 600-frame synthetic GUI/voice/recording run reported mean core frame latency
**1.3428865 ms**, wall duration **23.5862858 s**, and observed loop throughput
**25.4385114 frames/s**. These measurements include inference substitutes; loop
throughput includes GUI pacing/startup/shutdown. They are not real YOLO,
MediaPipe inference throughput or an operational FPS guarantee.

That run's skip warning device-start estimate was **300.0567087 ms** after dispatch.
This is one actual sample, not a latency bound or benchmark. Real full-pipeline
YOLO FPS, recognition accuracy, astronaut/microgravity performance: not measured.

## Offline evidence and limitations

Cloud dependency in the full runner: **NO**. Internet required after complete
setup/assets: **NO**. External downloads attempted in executed runtime modes:
**NO**. The guard intercepts Python socket connect/connect_ex/create_connection;
it does not disable network adapters or guarantee every native library path.
Physical internet disconnection remains a SIH hardware-demo checklist item.

Actual YOLO execution is unverified. Existing owner code enforces local weights,
local tracker settings, disabled auto-install and offline Ultralytics checks.
The optional stream is a local server, not an outbound cloud dependency. SAPI5
and MediaPipe use installed OS/local assets. No cloud or VLM adapter is created.

## Compatibility changes and safety

| Owner change | Integration defect | Narrow fix | Evidence |
|---|---|---|---|
| `02_yolo/procedure/event_log.py` | Caught disk errors were invisible to system health; raw deque reads could race voice logging. | Expose last_error and a locked snapshot of bounded records; existing emit/close behavior retained. | Write-failure/concurrent-read tests and existing Module 02 procedure tests pass. |
| GUI state/adapter/camera widget | Live images were cropped and default demo rack axes overpainted actual calibrated overlays. | Carry overlays_rendered, skip duplicate GUI overlay, contain the source image. | GUI payload/offscreen tests and existing GUI smoke suite pass. |

No Module 01–06 perception algorithm, FSM transition, recovery policy, mirror
correction or shared event schema was changed.

## Final Git hygiene classification

- Required integration: runtime YAML, event-map YAML, activity adapter,
  full_cli/full_gui/full_synthetic/full_system/outputs, authoritative launcher,
  main alias, direct dependency versions.
- Required compatibility fixes: EventLog and the three GUI files above.
- Tests: three full-system test files and the offline-verification script.
- Documentation: root README, FULL_SYSTEM.md and this report.
- Unrelated existing user work changed/discarded: **none**.
- Generated videos/logs/screenshots: retained in ignored output directories;
  no generated source artifacts staged.

Final status is seven modified tracked files and fifteen untracked source/test/
documentation files. Staged diff is empty. `git diff --check` passes. Windows
LF/CRLF normalization notices are informational. `.gitignore` already covers
the runtime output locations, so no ignore-file change was necessary. Existing
tracked root media and historical fixtures were preserved.

## Acceptance still pending

The software integration and synthetic full-system demonstration are ready for
review. Full live acceptance remains blocked by absent trained experiment YOLO
weights, placeholder class IDs, and unvalidated red/yellow pick/place semantics.
The optional demo proxy maps contact/departure and does not prove lifting or
target placement. Physical camera open/close behavior and real experiment
recognition must be demonstrated before freezing the entire live system.

Known nonblocking issues: duplicate hand inference in 03/06, fixed-FPS recording
playback versus wall time, unauthenticated trusted-LAN streaming, bounded/drop
output queues, and native driver calls that may delay shutdown. No flight
certification or scientific physical-recovery safety is provided.
