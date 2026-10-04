# Module 02 acceptance record

This checklist follows the current shared contracts and
[integration decision](../perception/INTEGRATION.md). It replaces the superseded
plan assigning generic preparation, multi-frame stability and calibration to YOLO.
Exact verification results and limits are in [REPAIR_REPORT.md](REPAIR_REPORT.md).

- [x] Canonical PreparedFrame -> YoloPipeline -> canonical ObjectFrame.
- [x] Canonical Detection/BoundingBox leaves; no duplicate shared definitions.
- [x] Preserve source frame ID, capture timestamp, source/session and dimensions.
- [x] Original-source pixels; authoritative scale restoration applied once.
- [x] No duplicated Module 01 preprocessing or Module 03 reasoning.
- [x] Real local Ultralytics integration; one-time loading and clean close.
- [x] Existing .pt/.onnx file checks; runtime automatic installation disabled.
- [x] Import-time offline flags checked, including an already-online import.
- [x] CPU/auto/configured CUDA selection with mocked availability/index tests.
- [x] Configurable confidence/IoU thresholds and class whitelist.
- [x] Deterministic exact project/model class-map validation.
- [x] Empty output, invalid input, startup/runtime failures explicit.
- [x] Finite confidence and positive boxes; diagnostic clipping/rejection.
- [x] Optional backend IDs/reset; no invented identity or track quality.
- [x] Synchronous thread-safe lifecycle, model reuse, diagnostics/timing.
- [x] Legacy perception.detector delegates to the canonical backend.
- [x] Network-rejecting unit tests and actual Module 01/02/03 integration tests.
- [x] Documentation and smoke CLI follow implemented architecture.
- [x] Canonical/legacy import checks and syntax compilation pass.
- [x] Ruff lint/format checks and mypy on ten active source modules pass.

Deployment/evaluation gates, separate from implemented stage behavior:

- [ ] Supply trusted experiment-trained weights and final class IDs.
- [ ] Rerun native CPU offline smoke where Windows permits torch.dll to load.
- [ ] Validate optional ONNX/MPS and physical CUDA on target hardware.
- [ ] Evaluate experiment footage and tracker crossing/reacquisition quality.
- [ ] Measure target FPS/latency and detection quality on documented data.
- [ ] Complete independent teammate review.

Model-free tests do not establish recognition accuracy. Five historical footage
tracker cases remain skipped. Reference anchors stay empty; calibration belongs
to Module 03. No benchmarks or spacecraft qualification are claimed.
