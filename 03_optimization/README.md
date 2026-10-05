# Module 03 — Optimization Sequence

Module 03 turns noisy `ObjectFrame` observations into deterministic temporal
evidence for Module 04. It confirms sustained presence, tolerates brief detector
gaps, aggregates confidence, and publishes a bounded sequence. It does not run
YOLO, label experiment actions, or detect semantic activity boundaries.

This is an offline SIH demonstration prototype, not flight-certified software.
Accuracy, latency, FPS, and microgravity performance are **not benchmarked in
this implementation**.

## Pipeline and public APIs

```text
FramePacket -> Module 01 FrameProcessor -> PreparedFrame
  -> Module 02 YoloPipeline -> ObjectFrame
  -> Module 03 OptimizationSequence -> OptimizationOutputPacket
  -> Module 04 validate_boundary_input(packet, original_frame)
  -> boundary analysis -> HAR -> procedure FSM
```

Use the import-safe `optimization` package; its implementation directory remains
`03_optimization/`. No duplicate packet or detector classes are introduced.

```python
from optimization import OptimizationSequence
from optimization.config import load_config

optimizer = OptimizationSequence(load_config("configs/optimization.yaml"))
output = optimizer.process(object_frame)  # canonical shared ObjectFrame
for evidence in output.stable_detections:
    if evidence.observed:
        # A confirmed observation in THIS frame.
        pass
optimizer.reset()
```

The existing `OptimizationPipeline(config).process(prepared, objects)` API remains
the spatial integration wrapper used by `integration.chain.PerceptionChain`.
It composes the **same OptimizationSequence and PerceptionStabilizer**, adding
existing optional hands, injected pose, rack calibration, and geometric
interaction evidence. Both APIs use the same packet builder and temporal rules.
The object-only API neither requires pixels nor initializes those backends.

## Authoritative input

Reuse `shared.schemas.object_frame.ObjectFrame` and
`shared.schemas.observations.Detection`:

- Nonnegative integral `frame_id`; nonnegative finite `timestamp_s` in upstream
  monotonic source seconds. IDs and timestamps must strictly increase.
- Positive `image_width` and `image_height`, nonempty `source_id` and `session_id`.
- A list of detections (empty is normal), with nonnegative class ID, nonempty class
  name, finite confidence in [0, 1], and positive-area `BoundingBox` in original
  source pixels within image bounds.
- Optional nonnegative tracker ID, tracker status/quality/age and diagnostics.
  A tracker ID is never reassigned by Module 03.
- Upstream status, timestamps, dimensions, source/session, diagnostics, stage
  timings, and reserved reference-anchor metadata are preserved.

Invalid contracts raise `OptimizationInputError(ValueError)`; an incorrect
packet type raises `TypeError`. Validation precedes state mutation. This differs
from a well-formed frame reporting upstream `ERROR`/`INVALID_INPUT`: such a
frame ages state, publishes unusable output, and supplies no new observations.

The spatial wrapper first verifies all source metadata against `PreparedFrame`.
It retains Module 01's existing invalid-image behavior: rejected frames produce
`INVALID_INPUT` packets without temporal publication; accepted malformed images
age state using Module 01's missing count. Out-of-order rejected images do not
age state. Downstream must reject invalid packets.

## Authoritative output

`shared.schemas.optimization_packet.OptimizationOutputPacket` is the sole output
contract for both entry points. Existing fields remain usable:

| Field | Meaning |
| --- | --- |
| `object_frame.detections` | Detached, filtered **current** detections with Module 03 continuity/stability annotations; raw detector confidence remains unchanged |
| `observations` | Same current detections plus optional hands, poses, associations and interaction evidence |
| `spatial` | Matching shared spatial packet; empty optional features for the image-free API |
| `stable_detections` | Immutable confirmed evidence, including explicitly unobserved short-gap states |
| `temporal_window` | Tuple of the last `history_size` immutable `TemporalFrame` snapshots, oldest first |
| `raw_detection_count` | Input count before Module 03 filtering |
| `filtered_detection_count` | Low-confidence, lost/predicted, or unusable-upstream detections removed |
| `duplicate_detection_count` | Exact duplicate observations removed |
| `stable_detection_count` | Convenience property, derived from `stable_detections` (not an extra serialized field) |
| `quality_ok`, `reliable_for_temporal_reasoning` | Healthy processing and at least one currently observed, confirmed detection |
| `quality_reasons` | Nonempty when quality is false; warm-up/empty scenes are explicit |

A held object **never** enters current detections or generates a fresh interaction.
Consumers must inspect `observed`, `frames_since_seen`, and `last_seen_timestamp_s`
before using a held box. Held presence alone does not make quality true.

Each frozen `TemporalDetection` contains class/name, original bbox, tracker
identity/metadata, local continuity key, raw and aggregated confidence,
confirmation/presence flags, consecutive and accumulated hits, missing count,
and first/last observed frame IDs/timestamps. `TemporalFrame` carries frame/time,
upstream object-stage status, missing count before this frame, and active evidence.
Source/session/dimensions belong to the containing packet; context changes clear
the window. No images, upstream packets, or mutable detection leaves are buffered.

## Temporal rules

1. Validate the complete input before changing state.
2. Filter confidence below the configured threshold (equality is accepted).
   Tracker `lost` boxes and `frames_since_seen > 0` are missing evidence.
3. Suppress **exact** duplicates sharing class ID/name, bbox, and tracker ID.
   Keep the highest confidence, with first-occurrence tie breaking. Different
   tracker IDs always remain distinct, even at identical coordinates.
   Conflicting boxes/classes for the same tracker ID in one frame are invalid.
4. Reuse tracker IDs with class consistency. Without IDs, match same-class boxes
   by IoU against short-lived state. One-to-many/many-to-one ambiguity retires
   predecessor histories and starts new tentative identities.
5. Confirm after `detection_min_frames` consecutive accepted observations.
   A tentative miss clears its confirmation streak and EMA. After confirmation,
   presence remains latched until missing count exceeds `max_missing_frames`.
6. A missing frame never contributes a confidence score or detection hit.
   Frame-ID gaps age state; the spatial wrapper uses Module 01's authoritative
   missing count to avoid counting explicit drops twice.
7. Expire on missing count **greater than** the tolerance. Reappearance after
   expiry requires new confirmation. Tracker reclassification starts new state.
8. Publish immutable snapshots; old packets are unaffected by subsequent calls.

`consecutive_seen` resets on any miss. `observed_frames` follows the existing
confirmation count: the uninterrupted streak before initial confirmation, then
accumulated actual observations while confirmed. It excludes tolerated misses.

### Confidence aggregation

The selected strategy is the existing configurable EMA:

```text
first accepted score: aggregate = raw_confidence
later observation:   aggregate = alpha * raw_confidence + (1 - alpha) * aggregate
missing observation: aggregate unchanged; observed = false and missing count grows
```

For alpha 0.5 and scores 0.6, 1.0, 0.5, aggregates are 0.6, 0.8, 0.65.
This is an evidence score, not a calibrated probability of contact or presence.
Only `ema` is supported; unsupported strategy names fail clearly. No redundant
unbounded per-object confidence/bbox list is retained: EMA needs constant state
and the bounded window exposes historical values.

### Identity and orientation

`track_id` remains upstream-owned. A local `continuity_key` represents short
geometric continuity, not guaranteed physical identity. Untracked crossings can
restart confirmation; exact indistinguishable untracked duplicates collapse.
Two visibly distinct same-class instances are supported.

Matching uses IoU without interpreting camera up/down. Existing optional spatial
features use explicit rack-relative or image-diagonal units. Module 03 assigns
no PICK/ROTATE/PLACE activity labels.

## Configuration

Settings belong to `stabilization` in `configs/optimization.yaml` or
`configs/optimization_mock.yaml`. `StabilizationConfig` in `shared/config.py` is
authoritative; `optimization.config.OptimizationConfig` is only an alias.

| Setting | Default | Meaning |
| --- | ---: | --- |
| `min_detection_confidence` | 0.5 | Module 03 acceptance threshold; matches the repository's default detector floor |
| `detection_min_frames` | 3 | Consecutive observations required for confirmation |
| `max_missing_frames` | 2 | Missing observations retained before expiry |
| `history_size` | 12 | Processed-frame snapshot limit |
| `confidence_aggregation` | ema | Explicit aggregation strategy |
| `ema_alpha` | 0.5 | Weight of each new accepted confidence |
| `matching_iou_threshold` | 0.3 | Minimum IoU for untracked continuity |
| `max_time_gap_s` | 1.0 | Longer timestamp gaps clear temporal context |
| `max_detections_per_frame` | 256 | Reject larger packets before allocating temporal state |

Existing spatial settings `interaction_min_frames=4` and
`hand_matching_distance=0.1` remain configurable. Defaults are prototype
settings, not measured optima. Set confirmation to 1 and tolerance to 0 for
immediate presence with no retention.

Validate nonnegative tolerance, positive integral counts/limits, history at
least as large as confirmation, confidence in [0,1], EMA/IoU in (0,1], and a
positive finite time limit. The object-only YAML loader reads the same owner
file's temporal section; spatial sections are used only by the existing wrapper.

## Reset, state, memory and threads

`reset()` clears object/hand/interaction histories, windows, ordering cursors and
identity counters. Replaying identical inputs/configuration produces identical
object-only packets. Upstream supplied timing metadata is preserved; the spatial
wrapper's measured runtime timings naturally vary.

Switching source/session requires explicit reset. Resolution changes and time
gaps above the limit automatically clear temporal context and retain advancing
continuity counters to avoid reusing old keys within that run. Their reset
diagnostic is visible. The spatial wrapper also closes/reinitializes hand/pose
backends on reset. Static calibration configuration remains configured.

With input limit D, missing tolerance M and history H, object state contains at
most D*(M+1) entries and H snapshots, each with at most D*(M+1) evidence records.
Pair-distance deques in the optional spatial path are also bounded; hands/pairs
expire. Frame-ID gaps are aged in at most M+1 iterations.

One caller owns an optimizer instance. The repository's `PerceptionChain`
already serializes processing/reset with an RLock; the standalone optimizer
creates no threads and adds no redundant lock. Direct multithreaded callers
must serialize access.

## Module 02 and Module 04 integration

Module 02's SIH `YoloPipeline` returns the shared `ObjectFrame` directly.
No adapter, model weight, camera, or GPU is needed by Module 03. The original
input object/detection values are not mutated.

Module 04's actual `validate_boundary_input` accepts both entry points plus the
matching original `FramePacket`. It verifies nested metadata/coordinates,
current evidence versus the latest snapshot, stable membership, ordering,
presence flags, confidence, and detection accounting. It accepts healthy
warm-up, empty, and short-gap packets while quality remains explicit.
Module 04 now executes segmentation, contours and target selection in the real
milestone runner; see [the repair report](../MODULES_01_05_REPAIR.md).

## CLI and tests

Run from the repository root after installing existing local dependencies:

```bash
python -m optimization.standalone_cli --synthetic
python scripts/run_optimization.py --synthetic --output outputs/events/optimization.jsonl
python -m optimization.standalone_cli --input detections.jsonl --output optimized.jsonl
python -m optimization.standalone_cli --input detections.json --config configs/optimization.yaml
python -m pytest -q -p no:cacheprovider 03_optimization/tests tests/test_yolo_to_optimization.py tests/test_optimization_to_boundary.py tests/test_packet_contracts.py tests/perception
python -m pytest -q -p no:cacheprovider
```

JSON accepts one `dataclasses.asdict(ObjectFrame)` object or a list; JSONL accepts
one per line and streams it. The existing Module 02 standalone `{"objects": ...}`
envelope is also accepted. Status/diagnostic enums and nested dataclasses are
decoded into the same shared types. Invalid input exits 2 with a logged reason.
Output uses `dataclasses.asdict(OptimizationOutputPacket)`; stdout contains JSONL,
and logs go to stderr. File output is an explicit overwrite; an input/output
path collision is rejected. A replay failure can leave earlier output lines.

Tests use synthetic canonical packets and injected inference backends. They
cover confirmation, thresholding, gaps, expiry, independent instances, exact
duplicates, ambiguous continuity, reset, deterministic replay, immutable
history, bounded long runs, malformed contracts/configs, source discontinuities,
both integration boundaries, CLI replay, and processing with network calls
blocked. Existing pose/skeleton/gesture scaffold tests remain skipped.

## Ownership and limitations

Active temporal code: `optimizer.py`, `input/`, `temporal/`, and the shared
packet builder in `output/`. Existing spatial implementations remain in
`hands/hand_tracker.py`, `pose/pose_tracker.py`,
`reference_frame/coordinate_frame.py`, `interaction/`, and `pipeline.py`.

No heavy tracker, learned smoothing model, HAR logic, or cloud dependency was
added. No bbox interpolation/extrapolation is performed; held bboxes are stale
by design and flagged. IoU can lose continuity under rapid motion without IDs.
The bounded snapshot window contains processed frames, not every missing frame.
Performance and field accuracy are not benchmarked. Modules 01–05 execute via
`python scripts/run_fusion.py --synthetic`. The real optional body helper can be
enabled with `--pose-model` or `--pose-config`: `MediaPipePoseTracker` adapts the
existing local Module 06 backend without changing Module 03's packet types.
Pose is disabled by default; hand inference remains configured by
`configs/optimization.yaml` or `--hand-model`. Missing enabled models are startup
errors. Unused historical pose/skeleton/gesture planning files remain inactive.

See [PIPELINE.md](PIPELINE.md), [DEFINITION_OF_DONE.md](DEFINITION_OF_DONE.md),
[executed verification](VERIFICATION.md), and the
[authoritative integration contract](../perception/INTEGRATION.md).
