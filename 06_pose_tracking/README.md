# Module 06 — Live Pose & Hand Tracking

Offline CPU pose (33 joints) and hand (21 joints per hand) tracking for the SIH
prototype. This is not flight-certified BAS software or microgravity validation.
Module 06 owns landmark inference, confidence masks, EMA, coordinates and generic
hand geometry. It does not own YOLO, rack detection, HAR, procedure correctness,
FSM, alerts, logging services, GUI applications or streaming.

## Existing architecture and ownership

The authoritative package is `06_pose_tracking/`, imported as `pose_tracking`
through the existing root locator. `contracts.py` defines one `PoseFrame` type;
there is no second TrackingOutputPacket schema. `standalone.py` remains a direct
script compatibility entry point. No package restructure is needed.

`perception/hand_tracker.py` and `perception/pose_tracker.py` are compatibility
imports for Module 03 helpers. Module 03's optional pose helper already delegates
to Module 06's backend; its legacy hand helper remains unchanged. The new
integration adapter consumes Module 03's existing reference transform rather
than creating or detecting another workspace.

```text
FramePacket -> Module 01 FrameProcessor -> PreparedFrame
   -> MediaPipe Pose + Hand Tasks (one RGB conversion, synchronous VIDEO mode)
   -> source pixels -> confidence/visibility validity masks
   -> LandmarkStabilizer (EMA, bounded hold, detection streaks)
   -> normalized camera XY + optional calibrated rack XY; padded hand box
   -> PoseFrame -> downstream interaction/HAR (outside this module)
```

`TrackingIntegration.process(MilestoneResult)` also supports the actual Modules
01–05 result: it checks Module 05's `ActivityEvent` identity, retains the upstream
`PreparedFrame`, and consumes `optimization.spatial.reference_frame`. ActivityEvent
has no image. Tracking does not interpret or modify the activity label.

## Input contract

Use the existing Module 01 types, not a new frame dataclass:

```python
from perception.core import FrameProcessor
from shared.schemas.frame_packet import FramePacket
from pose_tracking import PoseHandTracker, load_config

packet = FramePacket(frame_id=0, timestamp_s=0.0, image=bgr_uint8,
                     width=bgr_uint8.shape[1], height=bgr_uint8.shape[0],
                     source_id="camera_0", session_id="demo", metadata={})
prepared = FrameProcessor().process(packet)  # shared.schemas.PreparedFrame
with PoseHandTracker(load_config()) as tracker:
    tracked = tracker.process(prepared, workspace=None)
```

`PreparedFrame(image, scale_x, scale_y, source, status, warnings, notices,
stage_timings_ms, missing_frames, reset_required, accepted)` is the real shared
contract. It retains its original FramePacket. Core input is PreparedFrame,
not a naked ndarray. None/empty/unsupported images are rejected by FrameProcessor
and produce an INVALID_INPUT PoseFrame without inference. Passing an unrelated
object to the typed tracker API raises TypeError; a source-less PreparedFrame
raises ValueError. Frame IDs and timestamps must increase within one source and
session; call `reset()` before switching streams.

Optional `workspace` is the shared `ReferenceFrameInfo`: `valid`, `reference_id`,
`image_to_reference_matrix`, `axes_pixels`, `source`, `verified_this_frame`,
`verified_timestamp_s`. A valid reference requires a finite nonsingular 3x3
source-pixel-to-rack homography. Invalid availability falls back to camera
coordinates; a malformed purportedly valid transform yields INVALID_INPUT.

## Output contract

The exact public fields (defaults and validation live in `contracts.py`) are:

```python
Landmark(index: int, name: str, x: float, y: float, z: float,
         visibility: float | None = None, presence: float | None = None,
         is_valid: bool = True, normalized_xy: tuple[float, float] | None = None,
         rack_xy: tuple[float, float] | None = None)

HandPose(handedness: str, landmarks: tuple[Landmark, ...],
         handedness_score: float | None = None, model_handedness: str | None = None,
         observed: bool = True, frames_since_seen: int = 0,
         consecutive_frames: int = 1,
         bbox: tuple[float, float, float, float] | None = None)

PoseFrame(frame_id: int, timestamp_s: float,
          body_landmarks: tuple[Landmark, ...] = (), hands: tuple[HandPose, ...] = (),
          body_detected: bool = False, body_frames_since_seen: int = 0,
          source_id: str = "camera_0", session_id: str = "default",
          image_width: int = 0, image_height: int = 0,
          status: ModuleStatus = ModuleStatus.OK, warnings: tuple[Diagnostic, ...] = (),
          processing_time_ms: float = 0.0, body_score: float | None = None,
          coordinate_frame: CoordinateFrame = CoordinateFrame.IMAGE_PIXELS,
          feature_coordinate_frame: CoordinateFrame = CoordinateFrame.NORMALIZED_IMAGE,
          reference_id: str | None = None, body_consecutive_frames: int = 0,
          inference_ms: float | None = None, metadata: dict = {}, input_mirrored: bool = False)
```

These are frozen dataclasses; dict defaults use a factory. Source metadata is
copied. `key` includes source/session/frame/time. Convenience accessors include
`has_observation`, `left_hand_detected`, `right_hand_detected`, `body_landmark(name)`,
`hand(side)`, `HandPose.wrist`, `palm_center`, and legacy raw `bbox_xyxy`.
`bbox` is padded and clamped to [0,width] x [0,height] pixel edges; None means no
usable box. A palm center needs all five valid palm joints, otherwise None.

## Coordinates and microgravity approximation

- Primary x/y: ORIGINAL source pixels, even when PreparedFrame was resized.
- `normalized_xy`: x/width, y/height in the camera image. Out-of-view positions
  may exceed [0,1]; retaining them is different from clamping boxes for rendering.
- z: backend-relative, unitless pseudo-depth. It is not metric or rack depth.
- `rack_xy`: optional normalized planar workspace coordinates from the supplied
  reference. Invalid joints have no rack XY. A projective horizon invalidates
  that joint rather than publishing infinity.
- `feature_coordinate_frame`: shared enum `normalized_image` or `rack_relative`;
  primary `coordinate_frame` is always `image_pixels`.

No camera top/bottom is assigned physical meaning. The consumer must use the
matching supplied calibration after a setup rotates. Tests cover synthetic
0/90/180-degree coordinate equivalence; they do not prove rotated human landmark
accuracy or performance in real microgravity. Rack-relative depth is unavailable.

## Landmarks, confidence, smoothing

All 33 MediaPipe pose joints are retained, including nose, shoulders, elbows,
wrists and hips. Hands retain wrist and thumb CMC/MCP/IP/TIP, plus
MCP/PIP/DIP/TIP for index/middle/ring/pinky. `landmarks.py` supplies names/indices
and skeleton connections; tests compare them with the installed Tasks API.

Low pose visibility or supplied joint presence sets `is_valid=False`, retaining
index topology. All-invalid pose output is not a fresh pose. Missing backend
scores remain None. Native Hand Tasks exposes handedness confidence, not a
per-joint detection confidence; backend detection/presence/tracking thresholds
are separate. Low/missing handedness confidence produces UNKNOWN while usable
hand geometry remains. Duplicate labels retain the strongest side and mark the
other UNKNOWN, avoiding two supposedly identical anatomical hands.

EMA uses `alpha * current + (1-alpha) * previous`; alpha=1 disables extra smoothing.
Invalid joints are never blended with valid history. Recovery from an invalid
joint starts from the current observation. Missing labeled hands/body may be
held for `max_hold_frames`, with observed=False / positive frames_since_seen;
then expire. Streaks reset on loss or frame gaps. Time gaps, reset requests and
inference failures clear stale history. State is bounded to three tracks.
UNKNOWN hands have no stable association, so they are not held or smoothed.
A side label is not a persistent person/hand identity; crossings can reset EMA.
Before hand EMA, candidate centroids are compared with both live tracks from a
snapshot of the previous frame. A candidate closer to the opposite track than
its labelled track starts fresh, so a nearby label swap cannot cross-blend the
two physical hands. This is an ambiguity reset, not a persistent identity or
anatomical relabelling claim. Normal EMA and stale/hold/jump rules are unchanged.

The legacy shared PoseObservation/HandObservation adapters cannot carry a
per-joint validity mask, so they omit incomplete results instead of exporting
invalid joints as trusted points. Fully valid results propagate rack coordinates.
Consumers needing partial landmarks should use PoseFrame directly.

## Mirroring

Inference and display are separate. `--mirror-display` reflects the display
image and drawing positions, then draws text normally so labels stay readable;
frame coordinates and handedness remain unchanged. Legacy `--mirror`
explicitly flips input BEFORE inference, sets input_mirrored=True, and therefore
changes the coordinate grid. Do not combine it with a second upstream flip.

The current Tasks version-1 bundle reports anatomical labels for Google's
unmirrored `right_hands.jpg` and reversed labels when that fixture is mirrored.
The prior legacy Solutions rule was incorrect for this backend. Default
`swap_handedness: null` now swaps only mirrored inference. An explicit bool
supports different/custom model conventions. Raw model labels remain auditable
in model_handedness; visually left/right position is never used to infer a side.
Check the actual demo camera convention with a known hand before the presentation.

Shared `HandObservation.handedness` means anatomical handedness after mirror
correction. Both Module 03's Tasks producer and Module 06's adapter publish the
same title-case Left/Right convention (None when unknown). `mirrored_input` is
metadata only; consumers must not swap handedness again.

## Dependencies, configuration and local models

Dependencies already exist: NumPy, OpenCV, PyYAML, MediaPipe Tasks. No new package
was required. Actual environment verified: Python 3.14.7, MediaPipe 1.0.1,
OpenCV 5.0.0, NumPy 2.5.3, PyYAML 6.0.3. This is an observed installation, not a
claim that every Python/platform combination supports these versions.

`config/pose_tracking.yaml` contains backend thresholds, visibility/presence,
handedness confidence, max_hands, EMA/hold/jump/time-gap and box padding. Values
are prototype defaults, not scientifically calibrated thresholds. YAML model
paths resolve relative to that YAML; CLI --pose-model/--hand-model overrides
resolve relative to the working directory. See [local model setup](models/README.md).
No models are fabricated, committed or downloaded by runtime code. If one
configured model cannot initialize, the other runs with DEGRADED diagnostics;
if neither can initialize, startup fails clearly and closes resources.

## Independent execution

Run from the repository root:

```bash
python -m 06_pose_tracking --source 0 --show --mirror-display
python 06_pose_tracking/standalone.py --source clip.mp4 --no-show --jsonl tracking.jsonl
python -m 06_pose_tracking --source clip.mp4 --show --draw-pose --draw-hands --max-hands 2
python -m 06_pose_tracking --source clip.mp4 --no-show --no-draw-pose --output annotated.mp4
python -m 06_pose_tracking --source 0 --pose-model /local/pose.task --hand-model /local/hand.task
```

`--camera 0` is retained. q/Esc quits, r resets. Optional `--yolo` calls Module 02;
it does not implement detection here. Inference models initialize once. Core
classes never call imshow. LatestFrameCamera retains one newest frame; video files
are sequential. EOF, Ctrl+C and camera failure close models, captures and writers.
Diagnostics expose measured inference_ms, total processing_time_ms and live-loop
FPS in the overlay; no benchmark number is promised. JSONL/output flags are
standalone diagnostics, not an experiment logging subsystem.
Local source existence or camera opening is checked before expensive model
initialization. VIDEO timestamps are reserved before task inference so a partial
pose/hand failure cannot cause a duplicate timestamp on the next submission.

## Main pipeline integration

```python
from pose_tracking import TrackingIntegration
milestone = existing_module01_to05_pipeline.process(packet)
tracking = TrackingIntegration(tracker).process(milestone)
# Pair tracking with milestone.upstream.objects for a downstream owner.
```

Executable headless compositions reuse the real Modules 01–05 implementations:

```bash
python -m pose_tracking.pipeline_runner --synthetic --max-frames 36 --output tests_tmp/module06-pipeline.jsonl
python -m pose_tracking.pipeline_runner --video clip.mp4 --model /local/experiment_objects.pt --pose-model /local/pose.task --hand-model /local/hand.task
```

Synthetic mode replaces inference only, with explicit synthetic diagnostics. It
executes the real contracts, optimizer, boundary, fusion, tracker filtering, EMA
and rack normalization, including observations and loss. The real full pipeline
also needs Module 02 weights. They are absent in this checkout; real Modules
01–06 YOLO execution is not claimed. The existing Module 03 hand helper remains
an additional inference pass in that composition; sharing its inference cache
would require a separately scoped ownership change.

## Tests and manual acceptance

```bash
python -m pytest -q 06_pose_tracking/tests
python -m pytest -q
python -c "import pose_tracking; from pose_tracking import PoseHandTracker; print('Module 06 import OK')"
```

Model-free fixtures block Python socket access. Real-model tests explicitly skip
missing local .task files; positive sample tests separately skip missing local
Google fixtures. No test downloads assets. See models/README.md for one-time
sample setup. Tests cover contracts, EMA/reset/loss, confidence masks, source-size
mapping, rotated homographies, boxes, failure isolation, mirror display, video
read/write, lifecycle and full synthetic integration. See
[verification checklist](DEFINITION_OF_DONE.md) for recorded runs and open checks.

Manual command: `python -m 06_pose_tracking --source 0 --show --mirror-display`.
Confirm skeletons follow motion, both known hands get correct labels, q/Esc exits,
and temporary loss recovers. Test one/both hands, crossing, each hand leaving,
partial body, person rotating, and rack/setup at 90/180 degrees with appropriate
calibration supplied through the API. These physical scenarios have not been
verified in this repair. Hand accuracy, occlusion tolerance and latency across
deployment machines are unmeasured; this is a hackathon approximation.
