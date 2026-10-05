# Module 06 — Definition of Done

Status as of 2026-10-05. `[x]` = verified by an automated test or a recorded run;
`[ ]` = not yet verified.

## Implementation

- [x] `PoseFrame` / `HandPose` / `Landmark` contract exists, frozen and self-validating
- [x] Body landmarks (33) extracted with MediaPipe Pose Landmarker, local model
- [x] Both hands (21 landmarks each), handedness kept, 0 / 1 / 2 hands handled
- [x] Body and finger skeleton connections render (`render_overlay`)
- [x] YOLO boxes (class, confidence, track ID) render on the same frame
- [x] `frame_id`, `timestamp_s`, `source_id`, `session_id` preserved from the input frame
- [x] PoseFrame and ObjectFrame from one PreparedFrame are pairable by exact key
- [x] Memory bounded: ≤ 3 tracks, no history, one-slot camera buffer
- [x] Models load once; no per-frame disk or network access
- [x] No HAR / FSM / gesture logic, no camera-up semantics
- [x] Module 03 untouched
- [x] Standalone `--camera 0` command, pose-only and `--yolo`
- [x] Q/ESC quit, R reset
- [x] Survives: no person, hand loss, person loss, empty YOLO, camera read failure,
      model init failure (tests), plus a 150-frame live camera run

## Verification

- [x] Module 06 tests pass (81, no webcam/GPU/display/network)
- [x] Full repository suite passes with Module 06 present
- [x] Real local models load and run (optional test + live headless camera probe)
- [ ] Visual checklist with a person moving in front of the camera
      (body follows, elbows/wrists, LEFT/RIGHT hands, fingers, loss/return recovery)
- [ ] Handedness mirror convention confirmed on the demo camera
- [ ] Runs with networking physically disabled (tests block sockets; not done at OS level)
- [ ] `PoseFrame` promoted to `shared/schemas` (integration owner)
