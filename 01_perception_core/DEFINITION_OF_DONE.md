# Definition of Done — Module 01 Perception Core

> Historical checklist for the original camera/orchestration scope, which is outside
> the requested perception-only implementation. The implemented Module 01 checklist
> and verification evidence are in [perception/VERIFICATION.md](../perception/VERIFICATION.md).

## Functional Requirements

- [ ] Frames can be captured from a live camera selected in `configs/camera.yaml`.
- [ ] Frames can be read from a local video file (offline replay) with the same interface.
- [ ] Every frame receives a strictly increasing, never-reused `frame_id`.
- [ ] Every frame receives a monotonic `timestamp_s`.
- [ ] The original source frame is preserved and never modified in place.
- [ ] Frame buffer supports lookup by `frame_id` and returns `None` for evicted frames.
- [ ] Packet queues are bounded and follow the configured overflow policy.
- [ ] Pipeline manager runs modules in the order 02 → 03 → 04 → 05 → Procedure FSM.
- [ ] Health monitor collects `ModuleStatus` and measured timing per module.
- [ ] Optional recording to `outputs/recordings/` works when enabled.

## Input Contract

- [ ] Camera source, requested resolution/FPS and buffering are read from `configs/camera.yaml`.
- [ ] Config with required values still `null` is rejected with a clear message.
- [ ] Video paths are relative to the repository root (no absolute paths).

## Output Contract

- [ ] Output uses `shared.schemas.frame_packet.FramePacket` (no local redefinition).
- [ ] `width`/`height` are the actual frame dimensions.
- [ ] `color_format` matches the actual image channel order.
- [ ] `dropped_frames_before` reflects known dropped frames.

## Unit Tests

- [ ] `tests/test_camera.py` implemented and passing (skip markers removed).
- [ ] `tests/test_frame_sync.py` implemented and passing.
- [ ] `tests/test_pipeline_manager.py` implemented and passing.

## Integration Tests

- [ ] Module 02 receives `FramePacket`s and returns `ObjectFrame`s with matching `frame_id`.
- [ ] Modules 03 and 04 can fetch the source frame from the frame buffer by `frame_id`.
- [ ] `tests/test_packet_contracts.py` passes.

## Error Handling

- [ ] Camera open failure produces a clear start-up error.
- [ ] Mid-run read failure produces `ModuleStatus.ERROR` without crashing the process.
- [ ] End of video file triggers graceful shutdown.
- [ ] A failing downstream module is reported and does not crash the pipeline.
- [ ] Queue drops are counted and logged.

## Configuration

- [ ] All Module 01 settings come from `configs/camera.yaml`.
- [ ] Chosen values are documented with the reason they were chosen.

## Performance Checks

- [ ] Actual capture resolution and FPS have been measured and documented on the target demo hardware.
- [ ] Per-module processing time has been measured and documented on the target demo hardware.
- [ ] Frame drop counts under a full pipeline run have been measured and documented.

## Offline Operation

- [ ] Module runs with networking disabled.
- [ ] No component downloads anything at runtime.

## Documentation

- [ ] `README.md`, `PIPELINE.md` and this file reflect the implemented behaviour.
- [ ] Threading / execution model decision is documented.
- [ ] Module loading strategy for numbered folders is documented.

## Final Acceptance Criteria

- [ ] A recorded demo video runs through Module 01 end-to-end offline with correct `frame_id` / timestamp behaviour.
- [ ] Downstream modules can consume `FramePacket` without modification of the shared schema.
- [ ] Module owner and at least one other teammate have reviewed this checklist.
