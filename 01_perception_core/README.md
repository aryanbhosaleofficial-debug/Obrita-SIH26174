# Module 01 — Perception Core

The sole implemented Module 01 is [`perception/`](../perception/README.md).
Its authoritative [integration contract](../perception/INTEGRATION.md) defines
`FramePacket -> FrameProcessor -> PreparedFrame -> Module 02`.

Module 01 owns validation, copy-safe preprocessing, reversible geometry and the
shared coordinate/status/identity/configuration conventions. Camera capture,
application orchestration, model inference, optimization, boundary analysis,
HAR and FSM belong to their respective components.

Camera, synchronization, buffering and pipeline files under this numbered folder
are **inactive historical placeholders**. Their old docstrings/TODOs describe an
abandoned ownership plan and must not be treated as a second API or implemented
under Module 01 without a new architecture decision. Existing skipped tests are
preserved; none was removed to obtain a passing result.

Executable examples live in `examples/`; application composition lives in
`integration/`; actual regression tests live in `tests/perception/`.
