# Module 01 — Perception Core

Module 01 is the frame and contract foundation. Its public processor is
`perception.core.FrameProcessor`: `FramePacket -> PreparedFrame`.
The authoritative [integration decision](INTEGRATION.md) supersedes the former
combined inference pipeline. [Verification evidence](VERIFICATION.md) records
what was actually run.

## Ownership and entry points

| Owner | Implemented entry point | Output |
|---|---|---|
| External camera/video source | `examples/perception_camera.py` example | `FramePacket` |
| 01 foundation | `perception.core.FrameProcessor` | `PreparedFrame` |
| 02 YOLO | `yolo.pipeline.YoloPipeline` | `ObjectFrame` |
| 03 optimization | `optimization.pipeline.OptimizationPipeline` | `OptimizationOutputPacket` with `SpatialFeaturePacket` |
| Application composition | `integration.chain.PerceptionChain` | All three real stage packets |
| 04 receiving boundary | `boundary.input.input_validator.validate_boundary_input` | Validation or `BoundaryInputError` |

YOLO inference/tracking lives in `02_yolo/`; hands, calibration, continuity,
association and confirmation live in `03_optimization/`. The import-safe `yolo`,
`optimization`, `boundary` packages locate those numbered directories without
copying code. Boundary analysis, HAR and FSM remain team-owned scaffolds.
`01_perception_core/` is a documentation/legacy scaffold directory; there is no
second Module 01 processor there.

## Run without models, camera or GPU

From the repository root, Python 3.11+:

```powershell
python -m pip install -r requirements-perception.txt
python -m examples.perception_demo --frames 8
python -m examples.perception_rotation_demo
python -m pytest tests/perception -q
```

The chain demo injects explicitly synthetic object/hand observations. All frame,
geometry, temporal, schema and boundary-input code is real. Its reference is
measured by OpenCV from generated ArUco pixels. It does not emit fabricated
`BoundaryOutputPacket` or HAR results.

## Module 01 API

```python
from perception import FrameProcessor
from shared.schemas import FramePacket

core = FrameProcessor.from_yaml("configs/perception.yaml")
prepared = core.process(FramePacket(0, 0.0, image, image.shape[1], image.shape[0],
                                   source_id="camera_0", session_id="experiment_1"))
# Pass prepared to yolo.pipeline.YoloPipeline.process.
```

Use monotonic capture seconds for live video and source presentation time for
recorded video. Integral NumPy IDs are accepted and normalized to Python int.
Input is uint8 HxWx3 BGR/RGB with accurate width/height. The source is never
modified; prepared pixels are BGR, optionally resized/equalized, with reversible
source-coordinate scaling. Backends return coordinates in prepared-image pixels;
Module 02/03 restore original-source pixels before publishing packets.

One processor/chain handles one ordered source/session. Call `reset()` before a
new video or experiment. Duplicate/out-of-order/foreign-source packets are rejected
without consuming temporal history. A malformed frame ages history; ID gaps and
`dropped_frames_before` use the larger missing count, without double counting.
Resolution changes and gaps above configured `max_time_gap_s` clear histories and
restart tracking backends. All processing is synchronous; application scheduling,
queues, recording and GUI dispatch remain outside Module 01.

## Real inference setup and profiles

Install `requirements-perception-inference.txt` during setup; select the torch
CPU/CUDA build appropriate for the machine. Keep one compatible OpenCV wheel
family with `aruco.ArucoDetector` (the requirements specify contrib >=4.7).
Download the MediaPipe Tasks bundle before disconnecting. No runtime download or
auto-install is allowed. Python/wheel compatibility must be checked on the target.

| File | Authority |
|---|---|
| `configs/perception.yaml` | Module 01 preprocessing only |
| `configs/yolo.yaml` | Real detector, local weights, class map and optional tracker |
| `configs/yolo_tracker.yaml` | Prototype tracker settings; replaceable local YAML |
| `configs/classes.yaml` | Exact experiment model ID/name mapping |
| `configs/optimization.yaml` | Hands, reference, interaction, continuity and debug |
| `configs/perception_demo.yaml` | Paths to those three owner configs |
| `configs/perception_mock.yaml` | Paths to core + explicit synthetic backend configs |

Paths resolve relative to each owning YAML file. The real demo requires
`02_yolo/models/experiment_objects.pt`, `models/hand_landmarker.task`, four visible
markers, and a completed `classes.yaml`. Experiment weights are absent and class
IDs remain team placeholders; real startup fails clearly until supplied. Weight
metadata must exactly match the project ID/name mapping. Do not label arbitrary
weights with experiment class names to bypass validation.

Real demo tracking is enabled; local `lap>=0.5.12` is checked at startup. Tracking
can be disabled or its adapter replaced. The public object contract does not
require ByteTrack. The current Ultralytics adapter permits ByteTrack or BoT-SORT
with ReID disabled; an injected `ObjectDetector` may implement another tracker.

```powershell
python -m examples.perception_camera --source 0 --config configs/perception_demo.yaml
# Or --source data/videos/local_video.mp4
python -m examples.perception_offline_check mediapipe
python -m examples.perception_offline_check yolo --tracking
```

The last command uses temporary **untrained** local weights unless `--weights`
and `--classes` are supplied. It verifies runtime plumbing with Python network
audit events rejected, not recognition quality.

## Reference strategy and demo parameters

`CoordinateTransformer` is the shared protocol. Module 03 provides manual and
ArUco implementations. Manual corners are in physical order origin, +x, +x/+y,
+y; static validity is configuration validity, never current-frame verification.
ArUco uses centers of IDs `[0,1,2,3]` in that same physical order. Print/place the
markers accordingly; no camera-vertical assumption is used. All four are needed
on each frame. Missing/duplicate required markers invalidate live geometry; the
chain exposes image-diagonal fallback and a runtime warning.

Rack coordinates span a unit square across configured corners/marker centers.
They express fractions of board axes, not metres. Rectangular boards therefore
need threshold tuning; this is not metric Euclidean reconstruction. Fallback
coordinates divide BOTH x and y by `hypot(width,height)`. `x/width,y/height` are
only display/manual-calibration coordinates, never fallback distance units.

Rack/image-diagonal proximity, contact, ambiguity and trend thresholds have
separate config sections. Speeds are coordinate units per second. The 500 ms
LEAVING window, detection/interaction confirmation counts and all thresholds are
configurable demonstration parameters, not experimentally validated constants.
Confirmation counts remain frame based; motion/trend rates and LEAVING expiry
use timestamps. LEAVING is a single confirmed-near -> far transition event;
returning near rearms it. Small dropouts retain state without outputting stale
observations. Object motion requires tracker-backed continuity and valid rack
coordinates.

Context classes (rack, experiment_board, payload by default) stay in association
output but do not compete with contained interactables. Equally plausible
interactables and their primitives remain visible with `ambiguous=True`.
These are 2D evidence candidates; they do not prove touch or manipulation.

MediaPipe uses synchronous Tasks VIDEO mode and increasing milliseconds derived
from source timestamps. Samples that cannot advance by a millisecond fail clearly.
Handedness is optional raw model output; `mirrored_input` records the configured
camera convention, and no handedness-based identity or silent image flip occurs.
Ambiguous crossings start new short-term keys instead of inventing persistence.

See INTEGRATION.md for exact status, reliability, confidence and migration rules.
The implementation is an offline orientation-aware ground prototype; trained
accuracy, real-scene performance, microgravity behavior and flight qualification
are not established.
