# Module 06 — Live Pose & Hand Tracking

Real-time body-pose and two-hand landmark tracking with a live skeleton overlay.
It is a **parallel perception branch**: it consumes the same `PreparedFrame` as
Module 02 (YOLO) and publishes a `PoseFrame` for the same source frame. It does
not use, modify or repurpose Module 03 (`03_optimization`).

This is an offline SIH demonstration prototype, not flight software.
Landmark accuracy has **not** been evaluated.

> Rack-relative rotation testing is only a prototype approximation and does not
> prove real microgravity performance.

## Why a new module (and why number 06)

| Option | Decision |
| --- | --- |
| Extend `03_optimization/pose` (has an empty `PoseTracker` hook) | Rejected: Module 03 is reviewed/frozen, and the brief requires a parallel branch, not a repurposed 03 |
| Put landmarks in `OptimizationOutputPacket` | Rejected: that packet is Module 03's contract |
| New numbered module | **Chosen.** `01`–`05` are taken, so this is `06_pose_tracking/` |

The numbered directory cannot be imported with a normal statement (repository
rule, enforced by `tests/test_packet_contracts.py`). Its import-safe name is
`pose_tracking`, registered by `standalone.bootstrap()`, the same technique
Module 02 uses. A root-level `pose_tracking/` locator like `yolo/` is a
proposed integration change (see [Integration requests](#integration-requests)).

## Architecture

```text
                    FramePacket (frame_id, timestamp_s, source_id, session_id)
                              │
                      Module 01 FrameProcessor
                              │
                         PreparedFrame
                 ┌────────────┴─────────────┐
                 ▼                          ▼
     Module 02 YoloPipeline        Module 06 PoseHandTracker
                 │                 (MediaPipe Pose + Hand Landmarker,
                 │                  VIDEO mode, then LandmarkStabilizer)
                 ▼                          ▼
            ObjectFrame                  PoseFrame
                 │                          │
     Module 03 (unchanged)                  │
                 │                          │
       OptimizationOutputPacket             │
                 └───────────┬──────────────┘
                             ▼
             future Interaction Fusion (pair by FrameKey)
                             ▼
                  Boundary / HAR / FSM (not here)
```

| File | Responsibility |
| --- | --- |
| `contracts.py` | `Landmark`, `HandPose`, `PoseFrame`, `FrameKey` (frozen, validated) |
| `landmarks.py` | 33 body / 21 hand landmark names and skeleton edges (checked against MediaPipe in tests) |
| `backends.py` | `MediaPipeLandmarkBackend` (the only MediaPipe code), `NullLandmarkBackend`, raw result types |
| `smoothing.py` | `LandmarkStabilizer`: optional EMA + short, explicitly flagged hold; constant-size state |
| `tracker.py` | `PoseHandTracker`: `PreparedFrame -> PoseFrame`, handedness, failure isolation, reset |
| `sync.py` | `frame_key`, `require_synchronized`, `pair_with_objects`, adapters to shared `PoseObservation`/`HandObservation` |
| `visualization.py` | `draw_pose`, `draw_hands`, `draw_objects`, `draw_status`, `render_overlay` (no inference) |
| `sources.py` | `LatestFrameCamera` (one-slot newest-frame buffer), local video/image reader |
| `cli.py`, `standalone.py`, `__main__.py` | Standalone preview |
| `config.py`, `config/pose_tracking.yaml` | Settings; model paths resolve relative to the YAML |

The detector never depends on the GUI: `tracker.py` imports no drawing code
and `visualization.py` imports no model code.

## Dependencies

All already in the root `requirements.txt`: `mediapipe` (Tasks API), OpenCV,
NumPy, PyYAML. Verified in this workspace with Python 3.11.16, mediapipe 1.0.1,
opencv 5.0.0, numpy 2.4.6. No PyTorch pose model is used. `--yolo` additionally
uses Module 02's existing Ultralytics stack.

## Models / assets and offline setup

| Model | Path (default config) | Source |
| --- | --- | --- |
| Pose Landmarker (lite) | `06_pose_tracking/models/pose_landmarker_lite.task` | official MediaPipe model page |
| Hand Landmarker | `models/hand_landmarker.task` (shared with Module 03) | official MediaPipe model page |

See [models/README.md](models/README.md) for URLs and checksums. One-time setup
with network, then the module runs with no network: models load once from local
files, a missing file is an `InitializationError` (never a download), and no
cloud API or remote inference exists. `*.task` files are git-ignored by the
root `.gitignore`, so each machine must install them.

## Input contract

`shared.schemas.prepared_frame.PreparedFrame` from Module 01, which must retain
its `source` `FramePacket`. Inference runs on `prepared.image` (possibly
resized by Module 01). Normalized model output is mapped to **original source
pixels** using the source width/height.

- Frames rejected by Module 01 produce an empty `INVALID_INPUT` PoseFrame and
  touch no state; Module 01's diagnostics are carried through.
- One ordered `(source_id, session_id)` per tracker; `frame_id` and
  `timestamp_s` must strictly increase. Call `reset()` before switching source.
- `reset_required` (Module 01 time gap / resolution change) clears smoothing and hold.

## Output contract — `PoseFrame`

```python
@dataclass(frozen=True)
class Landmark:
    index: int; name: str
    x: float; y: float            # ORIGINAL source pixels (may slightly exceed the image)
    z: float                      # model-relative depth, unitless, NOT metric
    visibility: float | None = None
    presence: float | None = None

@dataclass(frozen=True)
class HandPose:
    handedness: str               # "LEFT" | "RIGHT" | "UNKNOWN" (anatomical, after mirror handling)
    landmarks: tuple[Landmark, ...]   # exactly 21, wrist..pinky_tip
    handedness_score: float | None = None
    model_handedness: str | None = None   # raw model label, for audit
    observed: bool = True         # False = short hold of the last observation
    frames_since_seen: int = 0    # 0 iff observed

@dataclass(frozen=True)
class PoseFrame:
    frame_id: int; timestamp_s: float           # copied from the source FramePacket
    body_landmarks: tuple[Landmark, ...] = ()   # 0 or 33
    hands: tuple[HandPose, ...] = ()            # 0, 1 or 2 (at most one LEFT, one RIGHT)
    body_detected: bool = False                 # observed in THIS frame
    body_frames_since_seen: int = 0             # >0 = held body
    source_id: str; session_id: str             # copied from the source
    image_width: int; image_height: int
    status: ModuleStatus                        # OK / NO_DETECTION / DEGRADED / INVALID_INPUT / ERROR
    warnings: tuple[Diagnostic, ...]            # shared WarningCode diagnostics
    processing_time_ms: float
    body_score: float | None                    # mean visibility of an observed body
```

Every instance validates itself (landmark counts/order, finite coordinates,
scores in [0, 1], held/observed consistency, unique LEFT/RIGHT). Helpers:
`frame.key`, `frame.hand("LEFT")`, `frame.body_landmark("left_wrist")`,
`hand.wrist`, `hand.landmark("index_finger_tip")`, `hand.palm_center`, `hand.bbox_xyxy`.

| Situation | Result |
| --- | --- |
| No person, no hands | `NO_DETECTION`, empty tuples — not an exception |
| Hand / person leaves | Re-published as held (`observed=False`) for `max_hold_frames` (default 2), then removed |
| Returns to frame | Observed again on the first detection |
| Inference error on one frame | `ERROR` for that frame only; stream continues |
| One of the two models failed to load | Other keeps running; `DEGRADED` with `POSE_/HAND_TRACKER_FAILURE` |
| Both models fail to load | `InitializationError` at `initialize()` |

## Body and hand tracking

- **Body**: MediaPipe Pose Landmarker, `num_poses=1`, 33 landmarks (nose,
  eyes, ears, shoulders, elbows, wrists, hips, knees, ankles, feet, ...).
- **Hands**: MediaPipe Hand Landmarker, up to `max_hands` (default 2), 21
  landmarks each. Hands are keyed by handedness so LEFT and RIGHT state stay
  independent. Two hands with the same label: the higher score keeps it and
  the other becomes `UNKNOWN` (never smoothed or held).
- **Handedness and mirroring**: MediaPipe documents that its hand labels assume
  mirrored (selfie) input. With `input_mirrored: false` (raw webcam) labels are
  swapped to anatomical sides; `--mirror` flips frames before inference and keeps
  labels. `swap_handedness` overrides this. **Not yet confirmed on the demo camera.**
- **Smoothing**: MediaPipe VIDEO mode already tracks and smooths. On top,
  `smoothing_alpha` (default 0.7, `1.0` = off, CLI `--no-smoothing`) applies an
  EMA; a jump larger than `jump_reset_fraction` of the image diagonal restarts
  instead of blending.
- **No HAR**: no actions, gestures or camera-"up" rules (e.g. "wrist above
  shoulder") exist here. Coordinates are preserved as-is for rack-, payload- or
  object-relative reasoning downstream.

## Live-stream behaviour and performance design

- Synchronous VIDEO mode: one result per submitted frame, no callback queue.
- `LatestFrameCamera` keeps only the newest frame. When processing is slower than
  the camera, old frames are overwritten (counted as `dropped_frames_before` /
  frame-ID gaps, which Module 01 reports) so latency cannot accumulate.
- Capture timestamps use `perf_counter()`. Windows `time.monotonic()` ticks every
  ~15.6 ms; in a live test it gave consecutive 30 FPS frames identical
  timestamps and Module 01 rejected every other frame. A guard also keeps them
  strictly increasing.
- With `--yolo`, YOLO runs on a one-worker thread while pose runs on the main
  thread, on the same `PreparedFrame`. At most one frame is in flight.
- Models load once; per frame there is one BGR→RGB conversion and no disk or
  network access. JSON serialization happens only with `--jsonl`. State is at most
  one body + one LEFT + one RIGHT track, with no history deque.

## Standalone command

From the repository root (with the project `.venv`):

```bash
python -m 06_pose_tracking --camera 0              # live pose + hands
python -m 06_pose_tracking --camera 0 --yolo       # + Module 02 boxes (02_yolo/config/standalone.yaml)
python -m 06_pose_tracking --camera 0 --mirror     # selfie view
python 06_pose_tracking/standalone.py --source clip.mp4 --no-display --jsonl pose.jsonl
python -m 06_pose_tracking --source photo.jpg --output annotated.jpg --no-display
```

Keys: **Q / ESC** quit, **R** reset tracker state (smoothing, hold and MediaPipe
tracking; YOLO tracking too with `--yolo`). Closing the window also quits.
Options: `--config`, `--yolo-config`, `--no-smoothing`, `--camera-width/--camera-height`,
`--output` (`.mp4` or image), `--jsonl`, `--max-frames`. Exit code 2 = setup or
source failure with a one-line log reason; no traceback.

The overlay shows body skeleton (white edges, orange joints), LEFT hand (green),
RIGHT hand (blue), UNKNOWN (magenta), held parts (grey), YOLO boxes with class,
confidence and track ID, plus a status line and measured FPS.

## Integration with YOLO (Module 02)

```python
prepared = frame_processor.process(packet)      # Module 01
objects = yolo_pipeline.process(prepared)       # Module 02 -> ObjectFrame
pose = pose_tracker.process(prepared)           # Module 06 -> PoseFrame
pose, objects = pair_with_objects(pose, objects)   # raises FrameSyncError if not the same frame
display = render_overlay(prepared.source.image, pose, objects)
```

Pairing is exact equality of `(source_id, session_id, frame_id, timestamp_s)`,
not nearest-timestamp matching. Both coordinate systems are original source pixels.

## Integration with future hand–object fusion

A fusion stage receives `PoseFrame` + `OptimizationOutputPacket` (whose
`object_frame` keeps the same frame key) and can use, per frame:
wrist/fingertip landmarks (`hand.landmark("index_finger_tip")`), `hand.palm_center`,
`hand.bbox_xyxy`, `observed`/`frames_since_seen`, object `bbox`, `track_id`,
`frame_id`, `timestamp_s`. Held hands must not be counted as fresh contact
evidence. `to_hand_observations()` / `to_pose_observation()` produce Module 03's
existing shared observation types if a consumer prefers those (observed only by
default). Fusion should express proximity in object- or rack-relative units,
not camera up/down.

## Tests

```bash
python -m pytest -q -p no:cacheprovider 06_pose_tracking/tests
```

Add `--basetemp <writable dir>` where the system temp dir is not writable.
81 tests, with no webcam, GPU, display or network (network calls are blocked
by fixture):

| File | Covers |
| --- | --- |
| `test_pose_frame_contract.py` | Schema validation, empty/one/two hands, held semantics, frozen/serializable, topology vs MediaPipe |
| `test_pose_tracker_stage.py` | Metadata preservation, source-pixel mapping (incl. Module 01 resize), handedness config, two-hand independence, loss/return, failure isolation, upstream rejection/diagnostics, reset, load-once |
| `test_pose_smoothing.py` | EMA arithmetic, jump reset, hold expiry, time gaps, reset, bounded state over 5000 frames |
| `test_pose_sync.py` | Real Module 01 → Module 02 (`YoloPipeline`, injected mock detector) + Module 06 on the same `PreparedFrame`; mismatch rejection; shared-observation adapters |
| `test_pose_overlay.py` | Detached rendering, held/empty frames, skipped low-visibility joints, mixed-frame refusal |
| `test_pose_cli.py` | Latest-frame camera (fake capture): drop-not-queue, read failure, open failure, timestamp regression; headless CLI on generated video/image; YOLO-init failure fallback; missing models; entry points |
| `test_pose_real_models.py` | Optional: real local `.task` models on synthetic frames (skips if absent) |

## Limitations

- Landmark accuracy, robustness to lighting/occlusion/gloves and the handedness
  mirror convention have **not** been evaluated on the demo setup.
- The visual checklist (skeleton follows movement, hands track, recovery after
  leaving the frame) needs a person in front of the camera and was not performed
  by the implementer; see the completion report.
- Single person (`num_poses=1`). Monocular `z` is relative, not metric. World
  (metric-ish) pose landmarks are not exported.
- Hand identity is by handedness label only; a one-frame label flip can briefly
  move a track (the jump guard prevents blending across it).
- Pose and hands run sequentially in one thread; YOLO runs beside them.
  Throughput depends on the machine. No FPS claim is made beyond the measured
  values in the completion report.
- `PoseFrame` lives in this module until promoted to `shared/schemas`.
- Rack-relative rotation testing is only a prototype approximation and does not
  prove real microgravity performance.

## Integration requests

These changes are outside Module 06 and were **not** made:

- **SCHEMA CHANGE REQUEST**: promote `Landmark`, `HandPose`, `PoseFrame` and
  `FrameKey` from `06_pose_tracking/contracts.py` to `shared/schemas/pose_frame.py`,
  export them from `shared/schemas/__init__.py`, and add `PoseFrame` to the
  `PACKETS` list in `tests/test_packet_contracts.py`. Note: `PoseFrame` uses
  frozen tuples and has no `target_track_id` (it describes the operator, not an
  object). Shared `Landmark` (in `spatial_feature_packet.py`) is a different,
  mutable Module 03 type; the name clash should be resolved during promotion.
- **EXTERNAL CHANGE REQUIRED**: add a root locator `pose_tracking/__init__.py`
  (same 5 lines as `yolo/__init__.py`, pointing to `06_pose_tracking`) so other
  modules can `import pose_tracking` without the bootstrap.
- **EXTERNAL CHANGE REQUIRED**: root `README.md` module table and Technology
  table ("MediaPipe: 03A only") should list Module 06.
- **CROSS-MODULE ISSUE (Module 02)**: `02_yolo/inputs/opencv_source.py` stamps
  camera frames with `time.monotonic()`. On Windows this has ~15.6 ms resolution,
  so at 30 FPS consecutive frames can share a timestamp. Module 06 hit exactly
  this live (fixed locally with `perf_counter`). Module 02's owner should check
  whether its standalone camera path is affected.
