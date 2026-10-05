# Module 03 — implemented pipeline

This document supersedes the former spatial/gesture planning diagram. It
describes executed code; optional unconnected scaffold files are future work.

```text
Module 02 shared ObjectFrame
  |
  v
input/input_validator.py — types, values, bounds, metadata
  |
  v
optimizer.py — stream ordering, resets, dropped-frame ageing
  |
  v
temporal/temporal_filter.py — confidence/lost filtering, exact duplicate suppression
  |
  v
temporal/stabilizer.py
  | tracker identity or conservative same-class IoU continuity
  | temporal/multi_frame_confirmation.py — consecutive confirmation + EMA
  | missing tolerance, ambiguity retirement, stale expiry
  v
temporal/sequence_buffer.py — bounded immutable image-free snapshots
  |
  v
output/optimization_packet_builder.py + optimizer.py publication
  |
  v
shared OptimizationOutputPacket
  | current object_frame + spatial/observations
  | stable_detections (observed or explicitly held)
  | temporal_window + counts + health/reliability
  v
Module 04 input/contract_validator.py + matching original FramePacket
  v
Boundary analysis [team-owned scaffold] -> HAR -> procedure FSM
```

The existing `OptimizationPipeline.process(PreparedFrame, ObjectFrame)` first
pairs metadata via `input/input_synchronizer.py`, then uses the same
`OptimizationSequence` lifecycle/state. Its optional hand/pose/reference
processing runs before the shared stabilizer and publication. Hands and
detections are paired geometrically; no final experiment action is assigned.

Temporal-only callers use `OptimizationSequence.process(ObjectFrame)`. Spatial
callers use the existing `PerceptionChain`. These entry points share one
implementation and one output contract; they are not alternate trackers.

Time comes from upstream `timestamp_s`. Historical entries carry no pixels.
Current observations never contain held boxes. Module 04 must inspect presence
flags before using retained evidence. The README specifies exact thresholds,
confidence, error handling, reset and memory behavior.
