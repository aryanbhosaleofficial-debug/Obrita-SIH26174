# Module 01 — Perception Core Pipeline

## Overview

```text
     PREVIOUS (no upstream module): Camera device / local video file (data/videos/)
                                   │
                                   ▼
                    ┌──────────────────────────────┐
                    │ 1. Camera Capture            │  camera/camera_capture.py
                    │    + Frame Reader            │  camera/frame_reader.py
                    └──────────────┬───────────────┘
                                   │ raw BGR frame
                                   ▼
                    ┌──────────────────────────────┐
                    │ 2. Frame ID Assignment       │  synchronization/frame_id_manager.py
                    └──────────────┬───────────────┘
                                   │
                                   ▼
                    ┌──────────────────────────────┐
                    │ 3. Timestamp Assignment      │  synchronization/timestamp_manager.py
                    └──────────────┬───────────────┘
                                   │
                                   ▼
                    ┌──────────────────────────────┐
                    │ 4. FramePacket Creation      │  shared/schemas/frame_packet.py
                    └──────────────┬───────────────┘
                                   │
                                   ▼
                    ┌──────────────────────────────┐
                    │ 5. Frame Buffer              │  buffering/frame_buffer.py
                    └──────────────┬───────────────┘
                                   │
                                   ▼
                    ┌──────────────────────────────┐
                    │ 6. Packet Queues             │  buffering/packet_queue.py
                    └──────────────┬───────────────┘
                                   │
                                   ▼
                    ┌──────────────────────────────┐
                    │ 7. Pipeline Manager          │  pipeline/pipeline_manager.py
                    │    + Module Manager          │  pipeline/module_manager.py
                    └──────────────┬───────────────┘
                                   │ dispatch in order
     ┌─────────────────────────────┼──────────────────────────────────┐
     ▼                             ▼                                  ▼
 NEXT: FramePacket ──► 02 YOLO  NEXT: frame lookup ──► 03 Optim.   NEXT: frame lookup ──► 04 Boundary
                                   │
                                   ▼
                    ┌──────────────────────────────┐
                    │ 8. Frame Synchronization     │  synchronization/frame_sync.py
                    └──────────────┬───────────────┘
                                   │
                                   ▼
                    ┌──────────────────────────────┐
                    │ 9. Health Monitor            │  pipeline/health_monitor.py
                    └──────────────┬───────────────┘
                                   │
                                   ▼
                     logs/ (measured timings, status)
```

## Interfaces

| Direction | Interface | Contract |
|-----------|-----------|----------|
| Previous | Camera / video file | OpenCV `VideoCapture`; settings from `configs/camera.yaml` |
| Next | Module 02 — YOLO | `FramePacket` |
| Next | Module 03 — Optimization | `FramePacket` lookup by `frame_id` via frame buffer |
| Next | Module 04 — Boundary | `FramePacket` lookup by `frame_id` via frame buffer |
| Feedback | Modules 02–05 | `ModuleStatus` + measured timing → health monitor |

## Stages

### 1. Camera Capture + Frame Reader

- **Purpose:** Acquire frames from a live camera or a recorded video.
- **Input:** `configs/camera.yaml` (`source`, `capture`).
- **Processing:** Open `cv2.VideoCapture`; request width/height/FPS; read back actual values; read frames in a loop.
- **Output:** Raw BGR frame (`numpy.ndarray`), actual width/height.
- **Failure condition:** Device/file cannot be opened; read returns no frame; device disconnects.
- **Next component:** Frame ID Assignment.

### 2. Frame ID Assignment

- **Purpose:** Give each frame a unique identity used by every module.
- **Input:** Raw frame.
- **Processing:** Increment a per-source counter; record gaps for known dropped frames.
- **Output:** `frame_id` (int).
- **Failure condition:** Counter reuse or reset mid-session (must never happen).
- **Next component:** Timestamp Assignment.

### 3. Timestamp Assignment

- **Purpose:** Record when the frame was captured.
- **Input:** Raw frame + `frame_id`.
- **Processing:** Read monotonic clock; optional wall-clock string for logs.
- **Output:** `timestamp_s` (float, seconds), `wall_time_iso` (optional).
- **Failure condition:** Non-monotonic timestamps (e.g. from video metadata) — logged.
- **Next component:** FramePacket Creation.

### 4. FramePacket Creation

- **Purpose:** Package frame and metadata in the shared contract.
- **Input:** Frame, `frame_id`, `timestamp_s`, actual size, source id.
- **Processing:** Build `FramePacket`; no image modification.
- **Output:** `FramePacket`.
- **Failure condition:** Missing required fields → `ModuleStatus.ERROR`.
- **Next component:** Frame Buffer.

### 5. Frame Buffer

- **Purpose:** Keep recent frames so Modules 03/04 can fetch the source image for a `frame_id`.
- **Input:** `FramePacket`.
- **Processing:** Insert into bounded ring buffer; evict oldest when full.
- **Output:** Lookup `frame_id → FramePacket | None`.
- **Failure condition:** Requested `frame_id` already evicted → returns `None`, logged.
- **Next component:** Packet Queues.

### 6. Packet Queues

- **Purpose:** Decouple modules running at different speeds.
- **Input:** Any shared packet.
- **Processing:** Bounded FIFO; overflow policy from config.
- **Output:** Packets delivered in order to the next module.
- **Failure condition:** Queue full → drop or block per policy; drop counted.
- **Next component:** Pipeline Manager.

### 7. Pipeline Manager + Module Manager

- **Purpose:** Run modules in order and manage their lifecycle.
- **Input:** `FramePacket`s; module outputs.
- **Processing:** Dispatch 02 → 03 → 04 → 05 → Procedure FSM; start/stop modules; handle exceptions.
- **Output:** Packets handed to the next module; module statuses.
- **Failure condition:** A module raises or returns `ERROR` → mark module, continue in degraded mode where possible.
- **Next component:** Module 02 (data path); Frame Synchronization (control path).

### 8. Frame Synchronization

- **Purpose:** Ensure packets combined later all describe the same frame.
- **Input:** Packets from several modules with `frame_id` / `timestamp_s`.
- **Processing:** Match by `frame_id`; use timestamp only as a consistency check.
- **Output:** Matched packet sets; list of unmatched / stale packets.
- **Failure condition:** No match within the configured window → reported, never paired with another frame.
- **Next component:** Health Monitor.

### 9. Health Monitor

- **Purpose:** Observe module status and measure timing.
- **Input:** `ModuleStatus` + timing from every module.
- **Processing:** Aggregate, detect stalls / repeated failures, write logs.
- **Output:** Log entries in `logs/`; health summary.
- **Failure condition:** Log directory not writable → warn on console, keep running.
- **Next component:** None (terminal stage of Module 01).
