# Module 03 — Optimization / Sequence / Skeletization

The active `optimization.pipeline.OptimizationPipeline` consumes matching
`PreparedFrame + ObjectFrame` and produces `OptimizationOutputPacket` containing
`SpatialFeaturePacket` and canonical `OptimizationObservations`. Implementation
remains in this numbered folder; `optimization/` is its import-safe locator.

Current reusable implementation, relocated from the former combined pipeline:

- `hands/hand_tracker.py`: MediaPipe Tasks VIDEO, optional handedness/confidence.
- `pose/pose_tracker.py`: replaceable optional pose interface; no built-in pose model.
- `reference_frame/coordinate_frame.py`: manual and live four-marker ArUco reference.
- `interaction/associations.py`: all hand/object pairs, context and ambiguity.
- `interaction/primitives.py`: geometric evidence candidates, never semantic HAR.
- `temporal/stabilizer.py`: bounded continuity, confirmation, rates and LEAVING edges.

`configs/optimization.yaml` owns its settings. Reference and threshold units,
confidence semantics, statuses and identity are defined by the shared contracts.
Spatial and temporal maintainers can develop these sections independently; they
share the same `HandObservation`, `Detection`, `ReferenceFrameInfo` and packet
classes. No backend-specific objects cross the interface.

Body-pose inference, skeleton construction, gesture classification, learned HAR
and other unconnected scaffold files are future team work. Existing PIPELINE and
DOD plans are not claims of implementation. Module 03 does not acquire frames,
run YOLO or replace boundary/HAR/FSM algorithms.

See [the authoritative integration contract](../perception/INTEGRATION.md),
[configuration and runnable examples](../perception/README.md), and
[verified limitations](../perception/VERIFICATION.md).
