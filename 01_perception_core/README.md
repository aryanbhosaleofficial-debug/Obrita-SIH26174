# Module 01 — SIH26174 Perception Core

> Implementation status: **scaffold only**. Interfaces and responsibilities are defined; algorithms are not implemented.

## Purpose

Module 01 is the foundation of the pipeline. It acquires frames from the camera (or a recorded
video), gives every frame an identity (`frame_id`) and a capture time (`timestamp_s`), preserves
the original source frame, and orchestrates the other modules.

```text
Camera
   ↓
Frame acquisition
   ↓
Frame metadata (frame_id, timestamp_s, size)
   ↓
Synchronization
   ↓
Queues / buffers
   ↓
Pipeline orchestration
   ↓
Health monitoring
```

## Position in Main Pipeline

```text
Camera ──► [01 Perception Core] ──► FramePacket ──► 02 YOLO
                     │                     ├──────► 03 Optimization (source image via frame buffer)
                     │                     └──────► 04 Boundary     (source image via frame buffer)
                     └── orchestrates 02 → 03 → 04 → 05 → Procedure FSM, monitors health
```

Module 01 is the **first** module. It has no upstream module; its upstream is the camera / video file.

## Responsibilities

- OpenCV camera capture (live device) and recorded-video replay (offline testing).
- Assigning strictly increasing `frame_id` values.
- Assigning monotonic capture timestamps (`timestamp_s`).
- Preserving the original source frame (no in-place modification by anyone).
- Synchronizing packets from different modules by `frame_id`.
- Bounded frame buffers and inter-module queues, with explicit drop policies.
- Pipeline management: module order, start/stop, graceful shutdown.
- Module health: `ModuleStatus` collection, stalled-module detection.
- Timing instrumentation: measuring and logging per-module processing time.

## Non-Responsibilities

- YOLO inference or tracking (Module 02).
- Pose estimation, hand landmarks, gesture recognition (Module 03).
- Segmentation, contour detection, chain codes (Module 04).
- Evidence fusion, HAR classification (Module 05).
- Procedure-step validation (Procedure FSM).
- Any image preprocessing for a specific model (resizing, letterboxing, colour conversion).

## Inputs

| Input | Source | Notes |
|-------|--------|-------|
| Camera frames | OpenCV `VideoCapture` (device index) | Live operation |
| Video file frames | `data/videos/` (relative path) | Offline replay / testing |
| `configs/camera.yaml` | Repository | Source, requested resolution/FPS, buffering, recording |
| `ModuleStatus` + timing reports | Modules 02–05 | For health monitoring |

## Outputs

| Output | Consumer | Notes |
|--------|----------|-------|
| `FramePacket` (`shared/schemas/frame_packet.py`) | Modules 02, 03, 04 | Primary output |
| Frame lookup by `frame_id` (frame buffer) | Modules 03, 04 | Source image for ROI processing |
| Health / timing logs | `logs/` | Measured values only |
| Optional recordings | `outputs/recordings/` | When enabled in config |

## Internal Components

| Folder | File | Role |
|--------|------|------|
| `camera/` | `camera_capture.py` | OpenCV capture, actual vs. requested settings |
| | `camera_config.py` | Load/validate `camera.yaml` |
| | `frame_reader.py` | Common interface for live camera and video file |
| `synchronization/` | `frame_id_manager.py` | Strictly increasing `frame_id` |
| | `timestamp_manager.py` | Monotonic `timestamp_s` |
| | `frame_sync.py` | Match packets by `frame_id` |
| `buffering/` | `frame_buffer.py` | Bounded buffer, lookup by `frame_id` |
| | `packet_queue.py` | Bounded inter-module queues |
| `pipeline/` | `pipeline_manager.py` | Module order and data hand-over |
| | `module_manager.py` | Module lifecycle |
| | `health_monitor.py` | Status + timing instrumentation |

## Technology Stack

> This stack is chosen for the **SIH prototype**: offline demonstration, modular development and rapid
> iteration. It does **not** demonstrate spacecraft qualification, radiation tolerance, flight
> certification, real microgravity validation or mission reliability.

### Core Technologies

| Technology | Purpose | Required / Optional | Why Used |
|------------|---------|---------------------|----------|
| Python 3 | Pipeline orchestration, synchronization, frame metadata, buffering, module coordination, health monitoring, configuration, logging | Required | All downstream modules (YOLO, MediaPipe, OpenCV boundary processing, fusion) are Python-based, so packets can be passed **in-process** as typed objects with no serialization or inter-process layer. |
| OpenCV (`opencv-python`) | Camera capture, frame acquisition, reading/setting frame properties, video-file handling, frame conversion, optional local recording | Required | `cv2.VideoCapture` handles both live cameras and recorded video files through one API, works offline, and returns frames as NumPy arrays that every other module consumes directly. `cv2.VideoWriter` covers optional recording. |
| NumPy | Image arrays, frame shape/dtype validation, lightweight geometry, metadata support | Required | OpenCV frames already are NumPy arrays; no conversion layer is needed. |
| PyYAML | Loading `configs/camera.yaml` and pipeline/module configuration | Required | YAML is human-editable and supports comments, which the placeholder configs rely on. `yaml.safe_load` does not execute arbitrary content. |
| Python standard library (`queue`, `threading`, `time`, `collections`, `dataclasses`, `enum`, `typing`, `pathlib`, `logging`) | Queues, workers, timestamps, buffers, typed packets, status, paths, diagnostics | Required (built in) | Everything a single-machine, in-process pipeline needs — no extra installation and no external services. |
| pytest | Camera, synchronization, packet-contract and pipeline tests | Development | Simple test discovery and skip markers for scaffolded tests. |

### Python Libraries

| Library | Used For | Module Component |
|---------|----------|------------------|
| `cv2` (opencv-python) | Open/read/release camera or video, request and read back width/height/FPS, optional `VideoWriter` recording | `camera/camera_capture.py`, `camera/frame_reader.py` |
| `numpy` | Frame array checks (shape, dtype), frame metadata | `camera/frame_reader.py`, `buffering/frame_buffer.py` |
| `yaml` (PyYAML) | `safe_load` of `camera.yaml` | `camera/camera_config.py` |
| `queue` | Thread-safe, bounded frame/packet transfer between pipeline components | `buffering/packet_queue.py` |
| `threading` | Camera acquisition worker and processing workers where appropriate; stop events for graceful shutdown | `camera/camera_capture.py`, `pipeline/pipeline_manager.py` |
| `time` | `time.monotonic()` for `timestamp_s`; `time.perf_counter()` for stage timing | `synchronization/timestamp_manager.py`, `pipeline/health_monitor.py`, `shared/utils/timing.py` |
| `collections` | `deque(maxlen=...)` ring buffer of recent frames; dict lookup by `frame_id` | `buffering/frame_buffer.py` |
| `dataclasses` | Typed shared packet (`FramePacket`) and config structures | `shared/schemas/frame_packet.py`, `camera/camera_config.py` |
| `enum` | `ModuleStatus` values | `shared/enums/module_status.py`, `pipeline/module_manager.py` |
| `typing` | Type hints on component interfaces | all components |
| `pathlib` | OS-independent relative paths for configs, videos, recordings, logs | `camera/camera_config.py`, `camera/frame_reader.py` |
| `logging` | Module diagnostics written to `logs/` | `pipeline/health_monitor.py`, `shared/utils/logger.py` |
| `pytest` | Tests | `tests/` |

### Required Technologies

- Python 3, `opencv-python`, `numpy`, `PyYAML`
- Standard library: `queue`, `threading`, `time`, `collections`, `dataclasses`, `enum`, `typing`, `pathlib`, `logging`
- Development: `pytest`

### Optional Technologies

- `multiprocessing` (standard library) — only if measurements show that thread-based execution cannot
  keep up. It adds the cost and complexity of passing frames between processes, so it is not part of
  the baseline.

### Future Optimization Technologies

- None planned. Module 01 performs no model inference, so inference runtimes (ONNX Runtime, TensorRT,
  OpenVINO) are not relevant here.
- If the default OpenCV capture backend behaves poorly on the demo machine, a platform-specific OpenCV
  backend can be selected through `capture.backend` in `camera.yaml` (still OpenCV, no new dependency).

### Recommended Stack Summary

| Technology | Purpose | Status |
|---|---|---|
| Python | Main implementation | Required |
| OpenCV | Camera/frame handling | Required |
| NumPy | Image/array operations | Required |
| PyYAML | Configuration | Required |
| Python `queue` | Packet/frame queues | Required (standard library) |
| Python `threading` | Worker execution where needed | Standard library |
| Python `logging` | Diagnostics | Standard library |
| pytest | Testing | Development |

### Not Used by Design

Kafka, RabbitMQ, Redis, Celery, ZeroMQ, ROS/ROS2, cloud messaging or any external broker. All modules
run in one process on one machine; packets move as Python objects through `queue.Queue` and in-memory
buffers. A broker would add installation, configuration and failure points without solving a problem
this prototype has.

## Technology Decisions

### Why These Technologies Were Selected

- **Python** — one language across all modules keeps the pipeline in a single process and keeps the
  codebase approachable for the whole team.
- **OpenCV** — one API for webcams and video files, so every module can be developed and tested offline
  on recordings with the same code path used for the live camera.
- **`queue` + `threading`** — the minimum needed to decouple camera acquisition from processing and to
  bound memory use, with no external infrastructure.
- **`time.monotonic()`** — immune to wall-clock adjustments, so frame ordering and time differences stay
  correct; wall-clock time is used only for human-readable logs.
- **PyYAML** — configuration stays outside code and can carry explanatory comments.

### Alternatives Considered

| Area | Alternative | Why Not Used Initially |
|------|-------------|------------------------|
| Camera / video I/O | Vendor camera SDKs, GStreamer pipelines, PyAV / imageio | Extra installation and integration effort; OpenCV already covers webcam and video files. Revisit only if the demo camera needs vendor-specific features. |
| Concurrency | `multiprocessing`, `asyncio` | `multiprocessing` requires copying or sharing frames between processes; `asyncio` is not a natural fit for blocking camera and model calls. Start simple and measure first. |
| Inter-module messaging | Kafka, RabbitMQ, Redis, ZeroMQ | Designed for distributed systems; a single offline process does not need a broker. |
| Orchestration framework | ROS / ROS2 | Large framework with its own build and runtime; not required for an in-process Python pipeline. |
| Configuration format | JSON, TOML | JSON has no comments; YAML is also used for procedure definitions, so one format serves both. |

## CPU / GPU Considerations

### CPU

Module 01 is CPU-only and runs no model inference. Its CPU costs are frame decoding, copying frames into
buffers and optional recording (video encoding). Buffer size × frame resolution determines memory use,
so `frame_buffer_size` should be chosen from measurements. Unnecessary frame copies should be avoided.

### GPU

Not used and not required. Module 01 must behave identically on machines with and without a GPU;
GPU-accelerated work happens in Modules 02 and 03.

### Hardware Considerations

- The actual resolution and FPS depend on the camera, driver and OpenCV backend. Module 01 logs the
  values actually delivered, which may differ from the requested ones.
- Camera acquisition shares the CPU with model inference in later modules. Whether every frame is
  processed or frames are dropped is a pipeline decision to be made from measurements.
- Runtime performance must be benchmarked on the final demo hardware.

## Offline Compatibility

After the dependencies are installed and the configuration is prepared (Module 01 needs no model files),
the module must **not** require internet access, cloud inference, external APIs or ground-station connectivity.

- Video sources, recordings and logs use local paths relative to the repository root.
- Logging writes to local files only; no remote log handlers.
- The module can be tested end-to-end on a recorded video in `data/videos/` without a physical camera.

## Shared Schemas Used

- Produces: `FramePacket`
- Reads for synchronization/health: `ObjectFrame`, `OptimizationOutputPacket`, `BoundaryOutputPacket`, `ActivityEvent` (only `frame_id`, `timestamp_s`, `status`)
- Enums: `ModuleStatus`
- Utils: `shared/utils/timing.py`, `shared/utils/logger.py`

## Configuration

`configs/camera.yaml` — source (camera index or video path), requested width/height/FPS, mirroring
flag, frame buffer size, queue size, overflow policy, recording flags, timing logging.

All values that must be decided by the team are `null` in the placeholder config.

## Dependencies

- Runtime: `opencv-python`, `numpy`, `PyYAML` + Python standard library (see [Technology Stack](#technology-stack)).
- Development: `pytest`.
- `shared/` package.
- No network, cloud services or message brokers.

## Developer Ownership

| Area | Owner |
|------|-------|
| Module 01 (all folders) | Teammate 1 — Perception Core *(name to be filled in by the team)* |

## How to Run Independently

Once implemented, from the repository root:

```bash
python scripts/run_camera.py
```

This should open the configured source, print the **actual** resolution/FPS accepted by the driver,
show frames with their `frame_id`, and optionally record to `outputs/recordings/`. Using
`source.type: video` allows testing without a physical camera.

## Testing

```bash
python -m pytest 01_perception_core/tests
```

| Test file | Covers |
|-----------|--------|
| `test_camera.py` | Config validation, offline video source, actual settings read-back, failure status |
| `test_frame_sync.py` | `frame_id` / timestamp monotonicity, packet matching, buffer eviction |
| `test_pipeline_manager.py` | Module order, graceful degradation, queue overflow, shutdown, timing |

All tests are currently skipped placeholders.

## Integration Contract

- Every frame gets exactly one `frame_id`; it is never reused within a session.
- `timestamp_s` is monotonic and assigned at capture time.
- `FramePacket.image` is the original frame at the actual capture resolution; downstream modules
  must never modify it in place.
- `width`/`height` are the actual frame dimensions (not the requested ones).
- Frame-buffer lookup for an evicted `frame_id` returns `None` — never a different frame.
- Dropped frames are visible as `frame_id` gaps and `dropped_frames_before`.
- Numbered module folders cannot be imported with `import`; the pipeline manager will load modules
  using the strategy agreed at integration time (see root `README.md`).

## Error / Failure Handling

| Failure | Behaviour |
|---------|-----------|
| Camera cannot be opened | Clear error at start-up; no silent fallback to another device |
| Frame read fails mid-run | `ModuleStatus.ERROR` reported; retry/stop policy documented |
| Video file ends | Explicit end-of-stream; pipeline shuts down gracefully |
| Queue full | Configured policy (drop oldest / block); drops counted and logged |
| Downstream module raises | Module marked `ERROR`; pipeline continues in degraded mode where possible |
| Non-monotonic timestamps | Logged as warning; ordering still by `frame_id` |

## Current Limitations

- Single camera source only.
- Threading model (sequential vs. threaded) not yet decided.
- Loading strategy for numbered module folders not yet decided.
- No measured timing data yet.

## Future Improvements

- Multiple synchronized cameras.
- Replay with original timestamps for realistic offline tests.
- Health dashboard / overlay (outside this scaffold's scope).
