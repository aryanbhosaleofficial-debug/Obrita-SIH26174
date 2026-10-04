# Definition of Done — Module 05 Perception Fusion

## Functional Requirements

- [ ] `OptimizationOutputPacket` and `BoundaryOutputPacket` are paired by `frame_id` and `target_track_id`.
- [ ] Object, gesture, interaction, motion, contact and boundary evidence are extracted.
- [ ] Evidence fusion is implemented using configured weights / rules.
- [ ] Missing evidence is treated as unknown, not as negative evidence.
- [ ] Conflicts between Module 03 and Module 04 evidence are resolved by the configured policy and recorded.
- [ ] Activities are confirmed over time; one continuous activity produces one event.
- [ ] Activity labels come from the configured label set.
- [ ] No procedure-order validation is implemented in this module.

## Input Contract

- [ ] Accepts `OptimizationOutputPacket` and `BoundaryOutputPacket` from `shared.schemas` only.
- [ ] Checks `frame_id`, `timestamp_s`, `target_track_id`, `status` and confidence ranges.
- [ ] Never modifies upstream packets.

## Output Contract

- [ ] Publishes `shared.schemas.activity_event.ActivityEvent` (no local redefinition).
- [ ] `start_frame_id <= end_frame_id`; timestamps consistent with frames.
- [ ] `evidence_summary` and `conflicts` are populated.
- [ ] `activity_label` values match `expected_activity` values used in `procedures/*.yaml`.

## Unit Tests

- [ ] `test_evidence_fusion.py` implemented and passing.
- [ ] `test_conflict_resolution.py` implemented and passing.
- [ ] `test_activity_event.py` implemented and passing.

## Integration Tests

- [ ] `tests/test_fusion_integration.py` implemented and passing.
- [ ] `ActivityEvent`s are accepted by `procedure/step_validator.py`.
- [ ] `tests/test_packet_contracts.py` passes.

## Error Handling

- [ ] Mismatched packets are never fused.
- [ ] Packets with rejected statuses or invalid confidences are rejected and logged.
- [ ] Missing boundary packet is handled per `allow_missing_boundary`.
- [ ] Insufficient evidence produces no false event.

## Configuration

- [ ] All thresholds, weights and policies come from `configs/fusion.yaml`; none hardcoded.
- [ ] Chosen values are documented with the recorded sessions they were tuned on.

## Performance Checks

- [ ] Fusion processing time per frame has been measured and documented on the target demo hardware.
- [ ] Event latency (activity end → event emitted) has been measured and documented on the target demo hardware.
- [ ] Activity recognition results have been evaluated on a documented, team-labelled set of recorded sessions, and measured results are recorded.

## Offline Operation

- [ ] Module runs with networking disabled.

## Documentation

- [ ] `README.md`, `PIPELINE.md` and this file reflect the implemented behaviour.
- [ ] Fusion method, conflict policy and activity vocabulary are documented.

## Final Acceptance Criteria

- [ ] On a scripted demo recording, each performed activity yields exactly one `ActivityEvent` with the correct label, verified by the team.
- [ ] Deliberately conflicting evidence produces a recorded conflict in the event.
- [ ] Procedure FSM consumes events without schema changes.
- [ ] Module owner and at least one other teammate have reviewed this checklist.
