# Module 05 executable pipeline

```text
OptimizationOutputPacket (shared)
+ BoundaryOutputPacket (shared)
    -> input/packet_validator.py: type, identity, status and confidence checks
    -> input/fusion_synchronizer.py: same frame/operator/timestamp
    -> evidence/object_evidence.py: unique current stable target
    -> evidence/{gesture,interaction,motion,contact,boundary}_evidence.py
    -> per-source thresholds from configs/fusion.yaml
    -> fusion/conflict_resolver.py: record/suppress or prefer confirmed boundary
    -> fusion/evidence_fusion.py: configured ordered all/any rules
    -> fusion/confidence_fusion.py: mean of available supporting scores
    -> har/activity_recognizer.py: candidate label or unknown
    -> temporal/evidence_buffer.py + activity_confirmation.py: N-of-M debounce
    -> har/activity_event_builder.py
    -> shared.schemas.activity_event.ActivityEvent
```

`pipeline.py` is the sole Module 05 orchestrator. Packet extraction is deterministic
and does not run inference. The rule is selected before temporal confirmation.
Unknown results carry no confirmed activity; ongoing confirmed results update the
current range but emit only once. `metadata.emitted` is the event delivery gate.

`integration.milestone.MilestonePipeline` composes the real Modules 01–05 interfaces.
`integration.cli.main`, called by `scripts/run_fusion.py`, owns capture, lifecycle,
JSONL diagnostics and event logging. The procedure FSM is an independently tested
consumer and is not run by this milestone command.

See [README.md](README.md) for defaults, conflict semantics and limitations.
