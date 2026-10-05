# Module 04 — Boundary Detection

Module 04 turns a current Module 03 target and original source pixels into
contour, chain-code, geometric, hand-proximity and confirmed temporal boundary
evidence. It imports the existing shared packets; no private schema, detector,
hand model, HAR, FSM, GUI, cloud service or model download is introduced.

This is an offline SIH prototype. Defaults are demonstration heuristics, not
scientifically validated thresholds. Accuracy, FPS and microgravity behavior
have not been benchmarked. It is not flight-certified software.
[REPAIR_REPORT.md](REPAIR_REPORT.md) records the independent-review repairs.
[MERGE_REPORT.md](MERGE_REPORT.md) is the historical pre-review recovery record.

## Canonical API

```python
from boundary.boundary_pipeline import BoundaryPipeline
from boundary.config import BoundaryConfig

pipeline = BoundaryPipeline.from_yaml("configs/boundary.yaml")
result = pipeline.process_optimization(optimization_packet, original_frame_packet)
pipeline.reset()  # before replay, source/session changes or a new experiment
```

The existing safe `boundary` package locates the numbered owner directory.
Dynamic `importlib.import_module("04_boundary.boundary_pipeline")` also works;
numbered names are invalid in normal Python import syntax.

The unchanged receiving contract validator checks Module 03 packets against
the retained original `FramePacket`: metadata, dimensions, detections, current/
stable/window consistency, hands and interactions. Source pixels must match
the source frame, not a resized PreparedFrame. It never treats a held box as
current evidence. Target selection requires an explicitly selected current
stable non-context detection, one unambiguous current interaction target, or
the sole eligible object. Ambiguity/no eligible target yields NO_DETECTION.

`target_track_id` is the operator ID; `target_object_track_id` is the selected
object ID. Existing object/hand continuity keys are reused, not independently
tracked. Multiple targets require explicit selection/individual instances.

Standalone callers can provide an explicit reference assertion:

```python
pipeline = BoundaryPipeline(config=BoundaryConfig(require_valid_rack_reference=True))
result = pipeline.process(image_bgr, 0, 0.0, roi=(20, 30, 80, 60),
                          target_object_track_id=7, rack_valid=True)
```

The boolean `rack_valid` is caller-supplied evidence; Module 04 performs no
calibration. It defaults false. The integrated path uses the canonical Module 03
reference validity. Rack orientation remains None even when the reference is
valid. `process_detections` accepts explicit original-pixel XYXY object boxes and
the same rack_valid keyword, without running inference. Normal process ROI is
original-pixel XYWH. Inputs are nonempty uint8 BGR/grayscale; integration also
converts RGB sources locally. Raw hand dictionaries contain finite pixel XY
points/landmarks and an optional stable hand ID.

## Conservative segmentation and confidence

1. Check raw grayscale ROI standard deviation before segmentation.
2. Threshold once and evaluate both binary polarities; adaptive also evaluates
   both. Canny outlines are filled into silhouettes before the same checks.
3. Apply configured morphology; require bounded foreground occupancy.
4. Require foreground/background separability: between-class variance divided
   by total raw grayscale variance. Uniform/weak-contrast noise is rejected.
5. Require a dominant connected component; reject fragmented noise.
6. Validate contour area/perimeter and its ROI-local border contact. A bbox
   spanning the ROI is rejected. Too many sides plus high border-point fraction
   is rejected. A normal object touching one edge is allowed.
7. Require consistency between foreground pixels and the filled contour, which
   rejects holes/background outlines. Select by segmentation score, not simply
   the largest candidate area.

Internal segmentation score is the minimum of separability, component dominance,
filled-contour foreground density and one minus the border-point fraction.
Final heuristic confidence is:
`segmentation_score * (0.50 + 0.25*solidity + 0.25*continuity_score)`,
where continuity uses the minimum of current and preceding accepted segmentation
scores, or zero without history. Solidity cannot override failed segmentation.
No interaction boost is used. These scores are not calibrated probabilities.

Rejected quality always publishes confidence=0, hand_contact=false,
contact_confidence=0, UNKNOWN and unconfirmed state. Invalid masks publish no
contour. Accepted segmentation subsequently rejected by rack/upstream/confidence
gates may retain geometry for debugging, with zero confidence/contact/state.
When only the confidence threshold rejects otherwise trusted segmentation,
bounded geometry history may warm continuity; it never casts state votes or
publishes contact until the complete public quality gate passes.

The foreground method remains an approximation for one isolated object in its
ROI, not instance segmentation. Tight boxes without background contrast, clutter,
occlusion and similar foreground/background colors may be conservatively
rejected. Pad/tune the ROI on local demo footage; there is no general guarantee
that all possible wrong contours are identifiable from pixels alone.

## Temporal boundary states and N-of-M confirmation

Only fully quality-accepted frames enter state classification. Geometry, centroid
and vote histories are bounded. Motion uses Euclidean image-plane centroid
displacement; it assumes a fixed demo camera, not physical camera-up or gravity.

| State | Candidate evidence |
|---|---|
| STATIONARY | At least motion_min_frames recent centroids; every displacement/source-frame interval <= stationary_tolerance_px |
| MOVING | Every recent displacement/source-frame interval >= moving_threshold_px and net displacement/path length >= min_motion_coherence |
| CONTACT | Valid geometry plus near-boundary evidence and contact proxy >= contact_min_confidence |
| SEPARATING | Previously confirmed CONTACT, same identified hand, release beyond contact range, distance exceeds contact anchor by configured increase, and coherent MOVING evidence |
| UNKNOWN | Warm-up, motion dead zone, ambiguous/no evidence or unconfirmed current candidate |
| ROTATING | Not implemented; never inferred from image-axis orientation |

CONTACT takes precedence over motion. Separation is a bounded transition lasting
at most confirmation_m valid released frames after the last confirmed contact;
it needs motion plus release evidence in multiple frames. Missing/replaced/
unidentified hands cannot establish that transition. Module 03 hand continuity
keys take precedence over its hand ID; standalone IDs are the caller's
responsibility. Proximity/contact/separation labels are image evidence, not proof
of a physical experiment event or procedure correctness.

The current candidate must occur N times in the last M valid candidate frames.
UNKNOWN never confirms. Defaults N=2/M=3 are anti-flicker demo settings.
`boundary_state` becomes the current candidate only upon confirmation;
`state_confirmed` is true then; `confirmed_frames` is its matching vote count
in the bounded window, otherwise 0. Old states are not published through a
changed/unconfirmed candidate. Invalid/absent geometry clears all semantic votes
and contact transition anchors immediately. More than max_missing_frames missing
IDs, large time gaps, resolution/target changes and reset clear semantic history; geometry retention
alone cannot carry a confirmed contact through invalid frames.

Missing IDs are counted as `current_frame_id - previous_frame_id - 1`: 10 to 12
means one missing frame. Gaps at or below the configured tolerance preserve valid
history; only actual accepted valid observations vote in N-of-M confirmation.
Motion displacement is divided by the source-frame ID interval so dropped frames
cannot inflate motion. These thresholds remain pixels per original source frame,
not pixels per second; FPS changes may require tuning. Timestamp ordering and the
separate max_time_gap_s reset still apply. Duplicate/backwards IDs are rejected.
Module 03's existing policy degrades packets when its own source frames are
missing; Module 04 continues to honor that upstream quality gate. Tests of real
Module 03 packets therefore also exercise packet drops between modules.

## Configuration

`configs/boundary.yaml` now has explicit prototype defaults. The loader is
read-only and validates known section/nested/parameter keys; unknown keys fail.
Null numeric settings resolve code defaults, including blur=3; explicit 0/1
disables blur. Existing nonnull wired settings remain configurable.

| Controls | Defaults |
|---|---|
| ROI padding_ratio / padding_px | 0.1 / 0 |
| blur_kernel, threshold params | 3, {} (Otsu when threshold omitted) |
| min_roi_stddev | 5 intensity units |
| foreground fraction min/max | 0.01 / 0.90 |
| min_component_dominance / min_contour_fill_fraction / min_separability | 0.80 / 0.85 / 0.80 |
| border_margin_px / max_border_sides / max_border_point_fraction | 1 / 2 / 0.35 |
| contour min area / max area / min perimeter | 20 / None / 0 pixels |
| morphology open / close / iterations / min component area | 0 / 0 / 1 / 0 |
| history_frames / max_missing_frames / max_time_gap_s | 20 / 2 / 1 second |
| motion_min_frames / stationary tolerance / moving threshold | 3 / 1 / 2 pixels per original source frame |
| min_motion_coherence / separation distance increase | 0.8 / 2 pixels |
| contact_distance_px / contact_min_confidence | 20 / 0.5 |
| confirmation_n / confirmation_m | 2 / 3 |
| min_confidence | 0.35 |
| require_optimization_quality / require_valid_rack_reference | shipped YAML true / true; standalone code rack gate false |

The integrated object bbox is padded by padding_ratio times its largest dimension
on each side, giving tight detections background context. Python and shipped YAML
both default to 0.1. ROI extraction clamps the padded coordinates to the image
bounds and rejects empty crops. Partial clipping remains subject to the unchanged
geometry quality gate; padding cannot recover background outside the image.
Standalone explicit ROIs retain their existing absolute padding_px behavior.

Legacy confirmation_min_hits/confirmation_window/stationary_tolerance are wired
aliases for n/m/stationary_tolerance_px; conflicting aliases fail explicitly.
Threshold parameters are threshold/invert (invert sets initial candidate order;
both polarities are still checked), adaptive block_size/c, or Canny low/high.
Connectivity must be 8. Start normalization and differential code default true.

Cross-check and hand-expanded ROI are **disabled**, and enabling either raises
a configuration error. HSV, non-none illumination, nonnull contour resampling or
rotation thresholds also raise explicit unsupported-feature errors. Empty
reserved HSV/illumination settings are allowed solely for compatibility.
Rack validity never invents orientation or current-frame calibration.

## Output, ownership and errors

The sole output is `shared.schemas.boundary_packet.BoundaryOutputPacket`.
Frame ID, seconds and identities survive. Contour/centroid geometry is in original
pixels. Dense contours remain unresampled despite the older shared comment;
the shared schema is unchanged. Freeman directions use image coordinates:
**+y downward**, numbered E, SE, S, SW, W, NW, N, NE (0 through 7). Closing edge
is included; cyclic normalization preserves steps. Histogram is eight normalized
bins. No camera angle is published as rack orientation. Crosscheck remains None.

A usable packet is OK; healthy absent/rejected segmentation is NO_DETECTION;
later quality rejection is DEGRADED; malformed raw inputs return INVALID_INPUT.
Preserved programmer contract mismatches in process_optimization raise
BoundaryInputError before temporal mutation. Ordering/new-stream operational
errors return INVALID_INPUT and retain prior valid state. This dual convention
is retained for compatibility rather than changing the receiver's API.

Use one instance per ordered stream and serialize process/reset calls.
New source/session requires explicit reset. Resolution changes/large time gaps
restart bounded histories. Only crops/color conversions and feature arrays are
owned; no source image/packet is mutated, no image is retained in history.
Reset clears order/context/target, geometry and all semantic state, allowing
deterministic replay.

## Offline runner and tests

```bash
python scripts/run_boundary.py --synthetic --frames 5
python -m boundary.standalone_cli --image local.png --roi 20 30 80 60
python -m boundary.standalone_cli --video local.mp4 --frames 120 --output local.jsonl
python -m boundary.standalone_cli --synthetic --config configs/boundary.yaml --rack-valid
python -m compileall 04_boundary shared
python -m pytest -q 04_boundary/tests
python -m pytest -q tests/test_packet_contracts.py tests/test_optimization_to_boundary.py tests/test_boundary_runtime_integration.py
python -m pytest -q 03_optimization/tests
python -m pytest -q
```

The CLI rack flag is an explicit caller assertion, not calibration. No weights,
YOLO, MediaPipe, Streamlit, camera or network is mandatory. Synthetic fixtures and
model-free stage packets exercise all reviewed scenarios, source/packet ownership,
state transitions, confidence/contact invariants and reset/boundedness. Only five
Module 04 tests remain individually skipped: HSV, multi-contour association,
resampling, rack rotation and optimization cross-check.

Module 04 -> Module 05 consumer verification is unavailable because Module 05
is not implemented. This is not a Module 04 runtime failure. Adding source/session
IDs to the boundary packet is a future centralized shared-schema request.
