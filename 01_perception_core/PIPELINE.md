# Module 01 pipeline

```text
External frame source -> shared.schemas.FramePacket
    -> FrameProcessor: source/session/order validation
    -> uint8 BGR preparation, optional resize/equalization
    -> shared.schemas.PreparedFrame (source retained, source scale, diagnostics)
    -> Module 02 YoloPipeline -> ObjectFrame
```

[Authoritative integration contract](../perception/INTEGRATION.md).
Module 01 performs no inference or temporal interaction processing.
