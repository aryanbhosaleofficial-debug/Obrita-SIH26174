# Module 04 repaired runtime

```text
Original FramePacket + canonical Module 03 OptimizationOutputPacket
  -> preserved receiving contract validation / explicit stream reset rule
  -> optimization quality gate / current stable target selection
  -> source-pixel ROI / 10% bbox padding clipped to image / grayscale information check
  -> threshold once + both polarities (or configured adaptive/Canny)
  -> morphology / occupancy / contrast separability / component dominance
  -> contour geometry + ROI-border checks + filled-contour consistency
  -> best segmentation-quality candidate / restore original-pixel offset
  -> closed image-y-down Freeman chain / cyclic normalization / differential / histogram
  -> geometry / nearest-hand image-distance evidence
  -> segmentation-weighted confidence / rack and upstream quality gates
  -> bounded STATIONARY / MOVING / CONTACT / SEPARATING candidates
  -> N-of-M confirmation for the current candidate
  -> canonical shared BoundaryOutputPacket
```

Rejected quality clears public confidence/contact/confirmed state. Invalid masks
publish no contour. Semantic history is never populated by invalid geometry.

Standalone process() and explicit-box process_detections() use the same core and
accept caller-supplied rack_valid. No calibration/model/inference is added.
process_optimization() uses the existing Module 03 reference and continuity keys.
The existing PerceptionChain orchestrator remains untouched.

Tolerated missing frame IDs preserve semantic history (current - previous - 1
<= max_missing_frames). Larger gaps still reset. Motion uses displacement divided
by the original source-frame interval; timestamp ordering/time-gap checks remain.
Only processed valid frames vote. Upstream quality rejection still clears state.

Rack-relative rotation/orientation, cross-check, HSV, hand-expanded ROI,
illumination and resampling remain unsupported; enabled unsupported features fail
configuration validation. Dense contours and image-coordinate Freeman convention
are documented without changing shared schemas. Module 05 consumer is unavailable.

See [README](README.md) for exact thresholds, state rules, error semantics and
[FINAL_P1_REPORT](FINAL_P1_REPORT.md) for the latest executed test evidence.
[REPAIR_REPORT](REPAIR_REPORT.md) preserves the earlier major-repair record.
