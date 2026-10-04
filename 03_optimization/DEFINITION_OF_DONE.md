# Definition of Done — Module 03 Optimization Sequence

Items are tagged **[T3]** (Teammate 3, spatial), **[T4]** (Teammate 4, temporal) or **[Both]**.

## Functional Requirements

- [ ] [T3] `ObjectFrame` and `FramePacket` are paired by `frame_id`.
- [ ] [T3] Operator and hand ROIs are generated from Module 02 detections.
- [ ] [T3] Body pose landmarks are produced from a locally stored model.
- [ ] [T3] Hand landmarks and handedness are produced (mirroring handled).
- [ ] [T3] Landmarks are validated, smoothed, and gaps are interpolated only within the configured limit and flagged.
- [ ] [T3] Skeleton bones are built from documented connection tables.
- [ ] [T3] Relative depth is represented as pseudo-3D (`z_rel`) and never described as metric.
- [ ] [T3] Rack reference is built from Module 02 anchors and marked invalid when unavailable.
- [ ] [T3] Landmarks are transformed into rack-relative coordinates when the reference is valid.
- [ ] [T4] Joint angles, displacement, velocity, acceleration and direction are computed from `timestamp_s`.
- [ ] [T4] Hand-object distance, association and proximity are computed.
- [ ] [T4] Gestures from the configured label set are recognized or reported as `unknown`.
- [ ] [T4] Interaction candidates use `InteractionState` values.
- [ ] [T4] Gestures and interactions require multi-frame confirmation.
- [ ] [T4] Quality gate sets `quality_ok` and records reasons.

## Input Contract

- [ ] [T3] Accepts `ObjectFrame` and `FramePacket` from `shared.schemas` only.
- [ ] [T3] Never modifies the source image in place.
- [ ] [T4] Accepts `SpatialFeaturePacket` from `shared.schemas` only.

## Output Contract

- [ ] [T3] Publishes `shared.schemas.spatial_feature_packet.SpatialFeaturePacket`.
- [ ] [T4] Publishes `shared.schemas.optimization_packet.OptimizationOutputPacket`.
- [ ] [Both] `frame_id` and `timestamp_s` are copied unchanged.
- [ ] [Both] Landmark pixel coordinates are in the original source frame.
- [ ] [T4] `object_track_id` values exist in the paired `ObjectFrame`.
- [ ] [T4] `quality_ok == False` always has at least one `quality_reasons` entry.

## Unit Tests

- [ ] [T3] `test_pose.py`, `test_hands.py`, `test_skeleton.py`, `test_reference_frame.py` implemented and passing.
- [ ] [T4] `test_motion.py`, `test_interaction.py`, `test_gesture.py` implemented and passing.
- [ ] [Both] `test_optimization_packet.py` implemented and passing.

## Integration Tests

- [ ] [T3] `tests/test_yolo_to_optimization.py` implemented and passing.
- [ ] [T4] `tests/test_optimization_to_boundary.py` implemented and passing (with Module 04 owner).
- [ ] [Both] Teammate 4 section runs on `SpatialFeaturePacket`s produced by Teammate 3 without changes.
- [ ] [Both] `tests/test_packet_contracts.py` passes.

## Error Handling

- [ ] [T3] No operator → packet published with `NO_DETECTION`, no crash.
- [ ] [T3] Missing reference anchor → `RackReference.is_valid = False`, no camera-up fallback.
- [ ] [T3] Missing model file → clear start-up error, no download.
- [ ] [T4] `frame_id` gaps do not produce velocity/acceleration spikes.
- [ ] [T4] Insufficient evidence → `unknown` gesture / `UNKNOWN` interaction.

## Configuration

- [ ] [Both] All thresholds come from `configs/optimization.yaml`; none hardcoded.
- [ ] [Both] Gesture labels are configurable.
- [ ] [Both] Chosen values are documented with the data they were tuned on.

## Performance Checks

- [ ] [T3] Pose and hand inference time per frame has been measured and documented on the target demo hardware.
- [ ] [T3] Smoothing lag has been measured and documented.
- [ ] [T4] Temporal section processing time has been measured and documented on the target demo hardware.
- [ ] [T4] Gesture / interaction recognition quality has been evaluated on a documented, team-collected set and measured results are recorded.

## Offline Operation

- [ ] [Both] Module runs with networking disabled.
- [ ] [T3] Pose/hand model files are loaded from local paths only.

## Documentation

- [ ] [Both] `README.md`, `PIPELINE.md` and this file reflect the implemented behaviour.
- [ ] [Both] Documentation uses "relative depth / pseudo-3D / relative XYZ", never "metric 3D" (unless calibrated depth is added).
- [ ] [T4] Distance measure, gesture approach and interaction rules are documented.

## Final Acceptance Criteria

- [ ] On a recorded demo video, skeleton and rack reference are visually correct on debug frames.
- [ ] Interaction and gesture outputs change as expected for a scripted demo sequence, verified by the team.
- [ ] Modules 04 and 05 consume `OptimizationOutputPacket` without schema changes.
- [ ] Both Teammate 3 and Teammate 4 have reviewed this checklist.
