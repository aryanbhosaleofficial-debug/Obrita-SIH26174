# Module 02 - YOLO object detection

Module 02 converts the canonical PreparedFrame from Module 01 into the canonical
ObjectFrame consumed by Module 03. This is an offline prototype architecture
intended to demonstrate the SIH26174 concept. It contains no activity, procedure,
boundary, GUI or gravity-direction reasoning.

```text
External source -> FramePacket -> Module 01 FrameProcessor
                                      |
                                PreparedFrame
                                      |
              MODULE 02: yolo.pipeline.YoloPipeline
                Check prepared image / restoration scale
                                      |
             Ultralytics model adaptation + local inference
                  (optional configured backend tracker)
                                      |
              Result parsing -> canonical Detection leaves
                                      |
               Confidence / class filter + box validation
                                      |
                 PreparedFrame.source_detection (once)
                                      |
                        Original-pixel ObjectFrame
                                      |
       Module 03 OptimizationPipeline.process(prepared, objects)
                                      |
                       OptimizationOutputPacket
```

Implementation stays in 02_yolo/. The existing yolo/ package locates this
directory; run examples/tests from the repository root. Legacy perception.detector
imports re-export the same adapter. See the authoritative
[integration contract](../perception/INTEGRATION.md), [stage details](PIPELINE.md),
[acceptance record](DEFINITION_OF_DONE.md) and [repair report](REPAIR_REPORT.md).

## Contracts and coordinates

| Contract | Authoritative definition | Module 02 use |
|---|---|---|
| PreparedFrame | shared/schemas/prepared_frame.py | BGR uint8 HxWx3 image, scale_x/scale_y, retained source, upstream status/diagnostics and reset signal |
| FramePacket | shared/schemas/frame_packet.py | Original source metadata/image, owned upstream |
| Detection, BoundingBox | shared/schemas/observations.py | ID, name, confidence, bbox=(x1,y1,x2,y2), optional backend ID |
| ObjectFrame | shared/schemas/object_frame.py | Original dimensions, metadata, detections, status, diagnostics and measured duration |

PreparedFrame has no direct frame_id or timestamp: those come from its source.
Output copies source.frame_id, timestamp_s, source_id, session_id,
width -> image_width and height -> image_height. No capture timestamp is generated.
Free-form metadata/orientation stays on prepared.source; ObjectFrame has no such
field. Shared contracts are unchanged.

Module 01 already converts RGB to BGR, optionally downsizes with rounded height,
and optionally equalizes luminance. It currently does **not** letterbox, crop or
rotate. Its actual independent x/y scales are used, including rounding effects.
Module 02 never repeats this preparation. Ultralytics performs model-specific
letterbox, color/tensor adaptation and NMS internally; Results.boxes.xyxy are
already restored to the image passed to inference. See the upstream
[prediction/result reference](https://docs.ultralytics.com/modes/predict/).

The parser produces prepared-image pixels. The stage filters/validates them there,
then calls the existing PreparedFrame.source_detection() once:
x_source=x_prepared/scale_x, y_source=y_prepared/scale_y. Published boxes are
original-source pixels, with 0 <= x1 < x2 <= image_width and equivalent y bounds.
No model-letterboxed, normalized or rack-relative boxes cross this stage.
Future crop/rotation support must update the authoritative upstream restoration
contract first; Module 02 cannot infer missing transform metadata.

## Installation and local weights

Use existing requirements and an isolated environment. Dependencies are intentionally
unpinned by repository policy until verified on demo hardware:

```powershell
# Repository root; setup needs cached wheels or internet.
.venv/Scripts/python.exe -m pip install -r requirements-perception.txt
# Real backends, including existing optional Module 03 dependencies:
.venv/Scripts/python.exe -m pip install -r requirements-perception-inference.txt
```

Module 02 needs NumPy, PyYAML, Ultralytics and a matching CPU/CUDA PyTorch build.
OpenCV is used upstream and by the CLI. Keep one compatible OpenCV wheel family;
see [environment setup](../perception/README.md). Tracking needs local lap>=0.5.12.
ONNX additionally needs a compatible preinstalled onnxruntime/onnxruntime-gpu
distribution. The adapter never installs dependencies at runtime. Do not blindly
add conflicting PyTorch/OpenCV distributions to a working environment.

Place trusted experiment-trained weights at 02_yolo/models/experiment_objects.pt
or configure another existing local .pt/.onnx file. Framework-required checkpoint
loading stays inside Ultralytics. Weights are ignored by Git.
See [model setup](models/README.md). Trained weights are absent and
configs/classes.yaml contains null placeholder IDs: supply both before real inference.

## Configuration

The existing schema is shared.config.DetectorConfig; the YAML section is
detector, not yolo. yolo.config.load_config() reads it once, snapshots settings
and rejects unknown fields. YAML paths are relative to the containing YAML file;
constructor/CLI paths are relative to the current directory. Create a new stage
to change settings rather than mutating configuration during inference.

The authoritative configs/yolo.yaml currently contains:

```yaml
detector:
  backend: ultralytics
  model_path: ../02_yolo/models/experiment_objects.pt
  classes_path: classes.yaml
  confidence_threshold: 0.50
  iou_threshold: 0.45
  class_whitelist: null
  device: auto
  cpu_fallback: true
  tracking: true
  tracker_path: yolo_tracker.yaml
```

| Setting | Behavior |
|---|---|
| backend | ultralytics for real inference; none explicitly disables it; mock requires an injected backend |
| model_path, classes_path | Required existing local weights and exact project class map |
| confidence_threshold, iou_threshold | Finite [0,1]; confidence rechecked after conversion; equality is retained |
| class_whitelist | null keeps all mapped classes, list selects IDs, [] keeps none; unknown IDs fail startup |
| device | cpu, auto, cuda, cuda:N or one nonnegative CUDA index; existing optional mps when available |
| cpu_fallback | Unavailable accelerator or accelerator inference failure can retry CPU with a warning; false enforces availability |
| tracking, tracker_path | Optional backend IDs; validated local ByteTrack/BoT-SORT YAML with ReID disabled |

Auto chooses CUDA 0 when available, otherwise CPU. An index beyond the available
CUDA device count is a startup error. Thresholds are repository defaults, not
experimentally optimized values. The shared schema has no image_size setting:
model-specific sizing uses the installed Ultralytics default.

classes.yaml requires a nonempty classes list with unique nonnegative integer id
and unique nonempty name. It must exactly match model metadata, including classes
excluded by whitelist; generic COCO weights cannot silently be relabelled.
Unknown/fractional IDs and per-frame mapping changes are rejected explicitly.
Core logic has no hardcoded demo colors or procedure-dependent filters.

## Usage and lifecycle

```python
from perception.core import FrameProcessor
from yolo.pipeline import YoloPipeline

processor = FrameProcessor.from_yaml("configs/perception.yaml")
with YoloPipeline.from_yaml("configs/yolo.yaml") as detector:
    # packet is supplied by the external source.
    prepared = processor.process(packet)
    objects = detector.process(prepared)
    # Existing Module 03: optimizer.process(prepared, objects)
```

initialize() loads/validates once; process() can initialize lazily for valid input.
A lock serializes initialization, inference, reset and close. Use one stage per
ordered source/session; the lock does not reorder concurrent submissions.
Module 01 owns sequencing. Its reset signal clears backend tracker history without
reloading weights. Explicitly reset the enclosing chain for source/session changes.
Context-manager exit closes the backend. There are no per-frame YAML reads,
model reloads, GUI operations or image dumps.

CLI smoke uses Module 01 and the same detector stage:

```powershell
python -m yolo --input data/raw/sample.jpg --weights 02_yolo/models/experiment_objects.pt --classes configs/classes.yaml --device cpu --no-tracking
python scripts/run_yolo.py --input data/raw/sample.jpg --device cpu
```

Supply sample.jpg locally. The CLI serializes ObjectFrame to stdout, logs to stderr,
and returns 0 for usable output, 1 for frame ERROR/INVALID_INPUT, 2 for setup/file errors.

## Offline and failure behavior

File existence and suffixes are checked before loading. The adapter sets
YOLO_OFFLINE=true and YOLO_AUTOINSTALL=false before importing Ultralytics and rejects
conflicting environment/library flags. If another component imports Ultralytics
first, set these variables at process launch. Offline state is read at import time;
see the [Ultralytics utility reference](https://docs.ultralytics.com/reference/utils/__init__/).
There are no cloud clients or external inference services. Install dependencies
and assets before disconnecting the network.

| Condition | Result |
|---|---|
| Missing/unreadable/incompatible weights, missing backend/runtime, bad class map/device/tracker | Actionable InitializationError, never permanently degraded startup |
| Wrong input type or missing retained source | TypeError/ValueError identifying caller misuse |
| Rejected upstream frame or invalid prepared image/scale | Empty INVALID_INPUT, no inference or initialization |
| Healthy empty scene | Empty detections, NO_DETECTION |
| Invalid confidence/class/ID/box row | Reject/count row; retain other valid rows with DEGRADED |
| Positive finite box partly outside image | Intersect with bounds and report clipped_count; wholly outside/collapsed boxes rejected |
| Malformed arrays, batch/shape/map mismatch, inference/reset failure | Empty ERROR with structured DETECTOR_FAILURE; later frames may recover |
| Tracking disabled or backend ID absent | Capability notice, no fabricated ID or degradation solely from the notice |

Order is preserved. Scores are uncalibrated confidence in [0,1].
The stage clears downstream stability/continuity/reference fields when creating
output leaves. It publishes no lost-object predictions, track quality or confirmation
votes. reference_anchors=[] is valid; Module 03 calibrates independently.
Backend IDs are session-local and reusable after reset, not permanent physical IDs.

stage_timings_ms["object_detection_ms"] measures inference/conversion/filtering,
excluding startup; invalid input records zero. Upstream diagnostics are copied.
Standard Python logging reports startup and debug-level frame diagnostics.
Module 03 merges preprocessing and detection timing separately and must check
unusable statuses before performing object-dependent reasoning.

## Testing and limitations

```powershell
.venv/Scripts/python.exe -m pytest 02_yolo/tests -q
.venv/Scripts/python.exe -m pytest -q --tb=short
.venv/Scripts/python.exe -m compileall -q 02_yolo yolo
# Optional developer tooling (mypy must already be installed):
.venv/Scripts/python.exe -m yolo.tests.verify_types
# Optional fresh-process real CPU/tracker/CLI smoke; requires installed backends:
python -m yolo.tests.verify_real_offline
```

Fixtures reject socket access, inject synthetic outputs and never download/load
real weights. Tests execute actual FrameProcessor, YoloPipeline and
OptimizationPipeline stages, covering metadata, coordinates, filtering, empty
frames, parsing, initialization, devices, model reuse/reset and recovery.

The optional type runner checks unchanged active sources under a temporary valid
package name because mypy does not follow the runtime yolo.__path__ locator.
It checks the ten active modules, excluding third-party internals and inactive
planning scaffolds. If the OS temporary directory is inaccessible, create
02_yolo/.verification and pass a fresh --basetemp directory below it to pytest.

The opt-in smoke makes temporary **random untrained** weights from an installed
YOLO11 architecture and denies/counts Python socket attempts. It verifies plumbing,
not accuracy, and is not collected by pytest. Five historical tracker-footage
scenarios remain skipped; backend identity/reset behavior is tested, physical
crossing/reacquisition quality is not.

Real smoke is currently blocked by Windows Application Control (WinError 4551
loading torch.dll). CPU/CUDA policies are tested with mocked framework outputs;
successful native inference, native-code network isolation, ONNX/MPS and physical
GPU execution are not claimed by this repair. Earlier Module 01 evidence is
historical, not a rerun of these changes.

Final experiment weights/classes and camera trials remain deployment work.
Accuracy, FPS and target-device latency: **not measured**. There is no spacecraft
certification or microgravity-validation claim.
