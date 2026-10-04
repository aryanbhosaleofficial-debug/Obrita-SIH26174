# Definition of Done — Module 02 YOLO

## Functional Requirements

- [ ] Model weights load from the local path in `configs/yolo.yaml`.
- [ ] Objects of the configured classes are detected on demo footage.
- [ ] Confidence and class filtering follow configuration.
- [ ] All output coordinates are in original source-frame pixels.
- [ ] Each tracked object keeps a persistent `track_id`.
- [ ] Track lifecycle (`tentative`, `confirmed`, `lost`, `reacquired`) is implemented.
- [ ] Track quality is computed and its definition is documented.
- [ ] Multi-frame stability (`is_stable`) is implemented.
- [ ] Rack / payload reference anchors are extracted when visible.

## Input Contract

- [ ] Accepts `shared.schemas.frame_packet.FramePacket` only.
- [ ] Never modifies `FramePacket.image` in place.
- [ ] Rejects `FramePacket`s with missing image or invalid size (`INVALID_INPUT`).

## Output Contract

- [ ] Output uses `shared.schemas.object_frame.ObjectFrame` (no local redefinition).
- [ ] `frame_id`, `timestamp_s`, `image_width`, `image_height` match the input `FramePacket`.
- [ ] All boxes satisfy `0 <= x1 < x2 <= image_width` and `0 <= y1 < y2 <= image_height`.
- [ ] Class names match `configs/classes.yaml`.
- [ ] `reference_anchors` is empty (not fabricated) when no anchor is visible.

## Unit Tests

- [ ] `tests/test_detection.py` implemented and passing.
- [ ] `tests/test_coordinate_restore.py` implemented and passing (all padding cases).
- [ ] `tests/test_tracking.py` implemented and passing.
- [ ] `tests/test_object_frame.py` implemented and passing.

## Integration Tests

- [ ] Module 01 → Module 02 run on a recorded video produces `ObjectFrame`s for every `frame_id`.
- [ ] `tests/test_yolo_to_optimization.py` implemented and passing.
- [ ] `tests/test_packet_contracts.py` passes.

## Error Handling

- [ ] Missing model file gives a clear error and no download attempt.
- [ ] Inference exceptions produce `ModuleStatus.ERROR` for that frame without stopping the pipeline.
- [ ] Invalid boxes are dropped and counted.
- [ ] Empty detections produce a valid `ObjectFrame` with `NO_DETECTION`.

## Configuration

- [ ] All thresholds come from `configs/yolo.yaml`; none are hardcoded.
- [ ] Classes and reference roles come from `configs/classes.yaml`.
- [ ] Chosen threshold values are documented together with the data they were tuned on.

## Performance Checks

- [ ] Inference time per frame has been measured and documented on the target demo hardware.
- [ ] Tracking time per frame has been measured and documented on the target demo hardware.
- [ ] Detection quality has been evaluated on a documented, team-collected evaluation set, and the measured results are recorded in `models/README.md`.

## Offline Operation

- [ ] Module runs with networking disabled.
- [ ] No automatic weight / config downloads occur (verified with network disabled).

## Documentation

- [ ] `README.md`, `PIPELINE.md` and this file reflect the implemented behaviour.
- [ ] `models/README.md` model record is filled in with measured facts only.
- [ ] Tracker choice and track-quality definition are documented.

## Final Acceptance Criteria

- [ ] On a recorded demo video, the operator, experiment objects and reference anchors are detected and tracked, with original-frame coordinates verified visually on debug frames.
- [ ] Module 03 consumes the `ObjectFrame` without any schema changes.
- [ ] Module owner and at least one other teammate have reviewed this checklist.
