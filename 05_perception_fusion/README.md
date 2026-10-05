# Module 05 — Perception Fusion

Implemented offline baseline: `fusion.pipeline.FusionPipeline` consumes the existing
shared `OptimizationOutputPacket` and `BoundaryOutputPacket`, then returns the shared
`ActivityEvent`. It recognizes evidence-supported actions, without judging procedure order.

```python
from fusion.pipeline import FusionPipeline

fusion = FusionPipeline.from_yaml("configs/fusion.yaml")
result = fusion.process(optimization_output, boundary_output)
if result.metadata["emitted"]:
    # Send this confirmed occurrence to a downstream consumer once.
    print(result.activity_label, result.confidence, result.evidence_summary)
```

Each call returns an explicit result. Insufficient, ambiguous, low-quality or
temporally unconfirmed evidence returns `unknown`, zero confidence,
`ModuleStatus.NO_DETECTION` and `metadata.emitted == False`. A confirmed continuous
activity keeps the same event ID and start identity while end identity advances.
Only its first confirmed result has `emitted == True`. The runner writes those
first confirmations to an events JSONL file; per-frame diagnostics retain all
current and unknown results. Event ranges describe the support interval through
the current frame, not a retrospectively determined final duration.

## Evidence and rules

The YAML vocabulary is `touch_object`, `move_object`, `rotate_object`,
`release_object`, `approach_object` and `unknown`. Rules have a name, label,
required `all` evidence, and optional `any` alternatives. Ordered rules express
priority. Rules, source thresholds, interaction priority, weights, speed threshold,
conflict policy and temporal settings live in `configs/fusion.yaml`; the example
procedure now uses vocabulary from that same file.

A unique, current stable non-context object with a track or local continuity key
is required. Held/ambiguous detections cannot confirm actions. A boundary target
track ID constrains selection. Multiple unresolved targets produce unknown.
Module 03's current interaction index selects only the target's observed,
unambiguous candidates; confidence unavailable from the source remains unavailable.
Confirmed gestures are extracted, and custom YAML rules can use them.

Motion consumes the selected object's measured `velocity_reference_frame` only
when `SpatialFeaturePacket.reference_frame.valid` is true. It is expressed in
rack units per second, not camera-up or metric motion. Boundary states contribute
only when quality-gated and confirmed; contact has its own positive confidence gate.
A missing optional source does not become a zero or a negative vote.

Confidence is the weighted mean of the sources that actually support the matched
rule. It is an explainable evidence score, not a calibrated probability. Rules
below the configured confidence threshold are discarded. The first eligible rule
wins. `evidence_summary` records source scores; metadata records normalized values,
candidate label, rule, source/session identity, confirmation and measured timing.

Explicit upstream disagreement, or moving/stationary disagreement between
rack motion and confirmed boundary, is recorded. Default `mark_uncertain` suppresses
confirmation. `prefer_confirmed_boundary` discards motion/interaction votes and
retains the confirmed boundary/contact evidence. Upstream packets are never changed.

## Temporal and error handling

The default is three hits in five frame IDs, with three unsupported frames ending
an occurrence. Gaps contribute no invented hits. Changing object/operator identity
clears history; large time gaps clear history. New source/session and replayed or
non-monotonic frames require an explicit `reset()`. Event counters stay unique
within an instance across resets. Unconfirmed results never emit events.

Mismatched frame, timestamp, operator, nested source/session, invalid confidence
or error/invalid-input statuses raise a concise validation error and break
confirmation history. Missing boundary packets are rejected unless
`input.allow_missing_boundary` is configured true. The milestone runner diagnoses
upstream model failures and publishes explicit unknown/invalid results instead of
trying to fuse unusable packets.

## Verification and limits

```bash
python -m pytest -q 05_perception_fusion/tests tests/test_fusion_integration.py
python scripts/run_fusion.py --synthetic
```

Fusion needs only Python and PyYAML; it loads no neural model and makes no network
calls. Synthetic tests cover identity, confidence, configured rules, conflicts,
noise, gaps, target changes, duplicate prevention, and real Modules 03/04 packet
consumption. The synthetic runner fakes only capture and model inference;
preparation, object filtering/restoration, rack transformation, stabilization,
association, boundary segmentation/features and fusion are real.

Baseline thresholds are prototype defaults. No labelled real-session accuracy,
target-hardware benchmark, microgravity validation or flight qualification is
claimed. Module 04 currently does not publish rack-relative ROTATING; the configured
rotation rule is independently packet-tested but cannot produce real rotation
events until that upstream feature exists. The baseline remains useful for touch,
motion, proximity and separation evidence.
