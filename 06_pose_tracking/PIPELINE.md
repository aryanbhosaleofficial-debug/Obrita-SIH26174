# Module 06 Pipeline — PreparedFrame → PoseFrame

```text
PreparedFrame (Module 01, source FramePacket retained)
  │
  ├─ 1. Type/source check ............ TypeError / ValueError (programming errors)
  ├─ 2. Upstream rejected? ........... yes → PoseFrame(INVALID_INPUT, Module 01 diagnostics), no state change
  ├─ 3. Same source/session? ......... no  → INVALID_INPUT (SOURCE_CHANGED); reset() first
  ├─ 4. frame_id / timestamp increase? no  → INVALID_INPUT (NON_MONOTONIC_FRAME)
  ├─ 5. reset_required? .............. yes → clear smoothing + hold (TEMPORAL_HISTORY_RESET)
  │
  ├─ 6. Backend (models loaded once)
  │      BGR → RGB (one copy) → MediaPipe Pose Landmarker  (VIDEO, num_poses=1)
  │                           → MediaPipe Hand Landmarker  (VIDEO, num_hands=max_hands)
  │      exception → PoseFrame(ERROR, POSE_TRACKER_FAILURE) for this frame only
  │
  ├─ 7. Normalized → ORIGINAL source pixels (x*width, y*height); invalid sets dropped
  ├─ 8. Handedness: model label → LEFT/RIGHT (mirror convention) → duplicate → UNKNOWN
  ├─ 9. LandmarkStabilizer (≤ 1 body + 1 LEFT + 1 RIGHT track)
  │      observed: EMA blend (alpha; jump → restart)
  │      missing:  held for ≤ max_hold_frames (observed=False), then dropped
  │      time gap > max_time_gap_s: clear
  │
  └─ 10. PoseFrame(frame_id, timestamp_s, source_id, session_id copied from source)
          status: warnings → DEGRADED; else OK if anything observed; else NO_DETECTION

Standalone loop (cli.py)
  LatestFrameCamera (1-slot, newest wins) → FramePacket → FrameProcessor
     → [YOLO on worker thread ‖ PoseHandTracker] on the SAME PreparedFrame
     → render_overlay (refuses mismatched frames) → imshow / --output / --jsonl
```
