# Definition of Done — Module 04 Boundary Detection

## Functional Requirements

- [ ] `OptimizationOutputPacket` is paired with the source frame by `frame_id`.
- [ ] The target object is selected from Module 03 interaction candidates using a documented rule.
- [ ] Boundary ROI is generated with configurable padding and correct offsets.
- [ ] Segmentation and mask cleanup produce a usable mask on demo footage.
- [ ] Target contour is extracted, associated, validated and resampled.
- [ ] Freeman chain code, start-point normalization, differential chain code and histogram are implemented.
- [ ] Orientation is computed relative to the rack reference and is `None` when the reference is invalid.
- [ ] Hand-boundary contact evidence is produced.
- [ ] `stationary`, `moving`, `rotating`, `contact` and `separating` states can be reported.
- [ ] Cross-check with Module 03 reports agreement without modifying Module 03 data.
- [ ] Multi-frame confirmation and quality gate are implemented.
- [ ] The module never decides procedure-step correctness.

## Input Contract

- [ ] Accepts `OptimizationOutputPacket` and `FramePacket` from `shared.schemas` only.
- [ ] Never modifies the source image in place.
- [ ] Handles `quality_ok == False` input as configured.

## Output Contract

- [ ] Publishes `shared.schemas.boundary_packet.BoundaryOutputPacket` (no local redefinition).
- [ ] `frame_id`, `timestamp_s`, `target_track_id` copied unchanged.
- [ ] Contour and centroid in original-frame pixels.
- [ ] `chain_code` values in `0..7`; numbering convention documented.
- [ ] `quality_ok == False` always has at least one `quality_reasons` entry.

## Unit Tests

- [ ] `test_segmentation.py` implemented and passing.
- [ ] `test_contours.py` implemented and passing.
- [ ] `test_chain_code.py` implemented and passing (synthetic shapes with known answers).
- [ ] `test_contact.py` implemented and passing.
- [ ] `test_boundary_tracking.py` implemented and passing.
- [ ] `test_boundary_packet.py` implemented and passing.

## Integration Tests

- [ ] `tests/test_optimization_to_boundary.py` implemented and passing.
- [ ] `tests/test_fusion_integration.py` passes with real `BoundaryOutputPacket`s (with Module 05 owner).
- [ ] `tests/test_packet_contracts.py` passes.

## Error Handling

- [ ] No target / empty mask / no contour produce a valid packet with `UNKNOWN` state and reasons.
- [ ] Invalid rack reference produces `orientation_deg_rack = None` without crashing.
- [ ] Evicted source frame produces `INVALID_INPUT`.

## Configuration

- [ ] All thresholds and ranges come from `configs/boundary.yaml`; none hardcoded.
- [ ] Tuned segmentation ranges are documented together with the lighting/setup they were tuned for.

## Performance Checks

- [ ] Per-frame processing time has been measured and documented on the target demo hardware.
- [ ] Boundary-state outputs have been checked against a documented, team-labelled demo recording, and measured agreement is recorded.

## Offline Operation

- [ ] Module runs with networking disabled.

## Documentation

- [ ] `README.md`, `PIPELINE.md` and this file reflect the implemented behaviour.
- [ ] Target-selection rule, contact rule and chain-code conventions are documented.

## Final Acceptance Criteria

- [ ] On a recorded demo video, debug frames show correct ROI, mask and contour for the target object.
- [ ] Scripted stationary / moving / rotating / contact / separating actions produce the corresponding states, verified by the team.
- [ ] Module 05 consumes `BoundaryOutputPacket` without schema changes.
- [ ] Module owner and at least one other teammate have reviewed this checklist.
