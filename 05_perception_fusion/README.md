# Module 05 — Perception Fusion

> Implementation status: **scaffold only**. Interfaces and responsibilities are defined; algorithms are not implemented.

## Purpose

Module 05 combines the landmark-based evidence from Module 03 and the boundary-based evidence from
Module 04 into a single, temporally confirmed **`ActivityEvent`** describing what the operator did.
The Procedure FSM then decides whether that activity was the expected procedure step.

## Position in Main Pipeline

```text
03 Optimization ──OptimizationOutputPacket──┐
                                            ├──► [05 Perception Fusion] ──ActivityEvent──► Procedure FSM
04 Boundary ──────BoundaryOutputPacket──────┘
```

## Responsibilities

- Synchronizing `OptimizationOutputPacket` and `BoundaryOutputPacket` by `frame_id` and `target_track_id`.
- Validating `frame_id`, `timestamp_s`, `target_track_id`, module status and confidence values.
- Extracting evidence: object, gesture, interaction, motion, contact, boundary.
- Evidence fusion and confidence handling (missing ≠ negative evidence).
- Conflict resolution between Module 03 and Module 04 evidence, with conflicts recorded.
- Temporal confirmation of activities (one event per activity occurrence).
- Activity recognition (HAR) over a configurable label set.
- Building `ActivityEvent`s.

## Non-Responsibilities

- Procedure-order validation (correct / wrong-order / skipped) — **Procedure FSM** (`procedure/`).
- Next-step suggestions — Procedure FSM.
- Re-running detection, pose, segmentation or any image processing (Modules 02–04).
- Modifying upstream packets.

### Important Boundary

Module 05 produces an **`ActivityEvent`** and nothing more. It does **not** decide:

```text
correct experiment step
wrong-order step
skipped step
next experiment step
```

Those belong to `procedure/` and the Procedure FSM, which consumes the `ActivityEvent`.

## Inputs

| Input | Source | Notes |
|-------|--------|-------|
| `OptimizationOutputPacket` | Module 03 | Includes pass-through `ObjectFrame` and `SpatialFeaturePacket` |
| `BoundaryOutputPacket` | Module 04 | Boundary state and contact evidence |
| `configs/fusion.yaml` | Repository | Thresholds, weights, conflict policy, temporal settings, activity labels |

## Outputs

| Output | Consumer | Notes |
|--------|----------|-------|
| `ActivityEvent` (`shared/schemas/activity_event.py`) | Procedure FSM | Primary output |
| Event log | `outputs/events/` | Written by the runner scripts |
| `ModuleStatus` + timing | Module 01 health monitor | |

## Internal Components

| Folder | Files | Role |
|--------|-------|------|
| `input/` | `fusion_synchronizer.py`, `packet_validator.py` | Pairing + validation |
| `evidence/` | `object_evidence.py`, `gesture_evidence.py`, `interaction_evidence.py`, `motion_evidence.py`, `contact_evidence.py`, `boundary_evidence.py` | Normalized evidence items |
| `fusion/` | `evidence_fusion.py`, `confidence_fusion.py`, `conflict_resolver.py` | Combine evidence |
| `temporal/` | `evidence_buffer.py`, `activity_confirmation.py` | Windowing + confirmation |
| `har/` | `activity_recognizer.py`, `activity_labels.py`, `activity_event_builder.py` | Label + event |

## Technology Stack

> This stack is chosen for the **SIH prototype**: offline demonstration, modular development and rapid
> iteration. It does **not** demonstrate spacecraft qualification, radiation tolerance, flight
> certification, real microgravity validation or mission reliability.

Module 05 works on **packets, not images**. Its baseline is explainable, rule-based fusion.

### Core Technologies

| Technology | Purpose | Required / Optional | Why Used |
|------------|---------|---------------------|----------|
| Python 3 | Orchestration and fusion logic | Required | Same language as the rest of the pipeline; upstream packets arrive as Python dataclasses. |
| NumPy | Feature vectors, confidence values, evidence aggregation, temporal arrays, simple numerical scoring | Required | Weighted scoring and aggregation over small arrays. |
| `dataclasses` / `enum` (standard library) | `ActivityEvent`, evidence structures, state representation, typed interfaces | Required (built in) | Typed, readable structures with no extra dependency. |
| `collections.deque` (standard library) | Temporal evidence windows, activity confirmation, short-term event history | Required (built in) | Bounded sliding windows without external infrastructure. |
| Rule-based evidence fusion (plain Python) | Initial fusion and activity recognition | Required (baseline approach) | Explainable and testable: every event can be traced back to the evidence that produced it. |
| PyYAML | Fusion thresholds, weights, conflict policy and HAR configuration from `configs/fusion.yaml` | Required | Tuning without code changes. |
| PyTorch (`torch`) | Learned temporal HAR classifier (LSTM / GRU / TCN / small Transformer) | Optional | Only if rule-based fusion proves insufficient on recorded, labelled sessions. |
| ONNX Runtime | Optimized inference for an exported learned HAR model | Future | Only after a learned model exists and is validated. |
| pytest | Fusion, conflict and event tests | Development | |

### Python Libraries

| Library | Used For | Module Component |
|---------|----------|------------------|
| `numpy` | Evidence vectors, weighted scores, confidence aggregation | `fusion/evidence_fusion.py`, `fusion/confidence_fusion.py` |
| `dataclasses` | Evidence item structures; `ActivityEvent` | `evidence/*`, `har/activity_event_builder.py`, `shared/schemas/activity_event.py` |
| `enum` | Evidence source and state representation | `evidence/*`, `fusion/conflict_resolver.py` |
| `collections.deque` | Evidence windows, confirmation, short event history | `temporal/evidence_buffer.py`, `temporal/activity_confirmation.py` |
| `uuid` | Unique `event_id` (or a session counter) | `har/activity_event_builder.py` |
| `yaml` (PyYAML) | `configs/fusion.yaml`, activity labels | `har/activity_labels.py`, `fusion/evidence_fusion.py` |
| `torch` *(optional)* | Learned temporal HAR layer, only if adopted | `har/activity_recognizer.py` |
| `pytest` | Tests | `tests/` |

### Rule-Based Evidence Fusion (Initial Implementation)

The first prototype combines several independent signals with explainable rules. Illustrative example
(labels are placeholders until the activity vocabulary is defined):

```text
object detected (stable target object)          ┐
gesture = rotate               (Module 03)      │
interaction = holding / manipulating (Module 03)├─► stronger evidence for a "rotate object" activity
boundary_state = rotating      (Module 04)      │    than any single signal alone
hand/object association valid  (Module 03)      ┘
```

Each source contributes according to configured weights and thresholds. Conflicts are resolved by the
configured policy and recorded in the event. A large black-box neural fusion model is **not** introduced
for the baseline.

### Required Technologies

- Python 3, `numpy`, `PyYAML`
- Standard library: `dataclasses`, `enum`, `collections.deque`, `uuid`
- Rule-based fusion logic
- Development: `pytest`

### Optional Technologies

- PyTorch learned temporal HAR layer (LSTM / GRU / TCN / small Transformer). It needs team-collected,
  labelled sessions; the rule-based baseline remains the reference implementation and fallback.

### Future Optimization Technologies

- ONNX Runtime for an exported learned HAR model, only after that model exists and is validated.

### Recommended Stack Summary

| Technology | Purpose | Status |
|---|---|---|
| Python | Main implementation | Required |
| NumPy | Evidence calculations | Required |
| dataclasses | Typed evidence/events | Standard library |
| enums | State representation | Standard library |
| `collections.deque` | Temporal evidence | Standard library |
| PyYAML | Fusion configuration | Required |
| PyTorch | Learned temporal HAR | Optional |
| ONNX Runtime | Future optimized HAR inference | Future |
| pytest | Testing | Development |

## Technology Decisions

### Why These Technologies Were Selected

- **Rule-based fusion** keeps every `ActivityEvent` explainable: the `evidence_summary` and `conflicts`
  fields show exactly why an event was produced, which is essential for debugging and for explaining results during the demo.
- **NumPy + standard library** are enough for weighted scoring over a handful of evidence sources.
- **`deque` windows** implement temporal confirmation simply and with bounded memory.
- **PyYAML** lets the team tune weights and thresholds on recorded sessions without code changes.

### Alternatives Considered

| Area | Alternative | Why Not Used Initially |
|------|-------------|------------------------|
| Fusion method | Learned neural fusion / end-to-end HAR model | Needs labelled training sessions, is harder to explain and test, and adds a model to manage offline. Kept optional. |
| Fusion method | Probabilistic models (e.g. Bayesian networks, HMMs) | Possible later refinement; more modelling effort than needed before baseline behaviour is understood. |
| Fusion method | Classical ML classifiers (e.g. scikit-learn) on fused features | Would add a dependency and require labelled data; considered only once features stabilize. |
| Event transport | Message brokers / event buses | Not needed: events are passed in-process to the Procedure FSM. |

No alternative is claimed to be worse; none has been benchmarked by the team.

## CPU / GPU Considerations

### CPU

The rule-based baseline operates on small evidence structures rather than images, and runs on the CPU.
Its cost must still be measured as part of the full pipeline.

### GPU

Not required for the baseline. A GPU could only help an optional learned PyTorch HAR model or a future
ONNX/TensorRT export of it; such a model must also be able to run on the CPU unless the team explicitly
decides otherwise.

### Hardware Considerations

- Event latency (from activity end to event emission) depends on the temporal confirmation window and
  must be measured.
- Runtime performance must be benchmarked on the final demo hardware.

## Offline Compatibility

After the dependencies are installed and the configuration is prepared, Module 05 must **not** require
internet access, cloud inference, external APIs or ground-station connectivity.

- The rule-based baseline uses **no model files**.
- An optional learned HAR model must be loaded from a local path only.
- Events are written locally to `outputs/events/`.

## Shared Schemas Used

- Consumes: `OptimizationOutputPacket` (incl. `ObjectFrame`, `SpatialFeaturePacket`), `BoundaryOutputPacket`
- Produces: `ActivityEvent`
- Enums: `ModuleStatus`, `InteractionState`, `BoundaryState`

## Configuration

`configs/fusion.yaml`: `input` (timestamp consistency, missing boundary policy, rejected statuses),
`evidence` (per-source minimum confidence), `confidence` (method, weights, missing-evidence policy),
`conflict_resolution`, `temporal`, `activities.labels`, `output`.

Weights and thresholds are `null` placeholders until validated on recorded demo sessions.
Activity labels must match `expected_activity` values in `procedures/*.yaml`.

## Dependencies

- Runtime: `numpy`, `PyYAML` + standard library (`dataclasses`, `enum`, `collections.deque`, `uuid`).
- Optional: `torch` (learned temporal HAR layer).
- Future only: ONNX Runtime.
- Development: `pytest`.
- No image-processing or detection dependency.
- `shared/` package. No network access. See [Technology Stack](#technology-stack).

## Developer Ownership

| Area | Owner |
|------|-------|
| Module 05 (all folders) | Teammate 6 — Perception Fusion *(name to be filled in by the team)* |
| `procedure/` (FSM) | To be assigned by the team (separate from Module 05) |

## How to Run Independently

Once implemented, from the repository root:

```bash
python scripts/run_fusion.py
```

Prints `ActivityEvent`s as they are confirmed and writes them to `outputs/events/`. Fusion logic can
also be developed against recorded / synthetic upstream packets, since all inputs are shared dataclasses.

## Testing

```bash
python -m pytest 05_perception_fusion/tests
```

| Test file | Covers |
|-----------|--------|
| `test_evidence_fusion.py` | Pairing, status / confidence validation, missing evidence, config weights |
| `test_conflict_resolution.py` | Module 03 vs 04 disagreement, conflict recording |
| `test_activity_event.py` | Shared schema, start/end frames, duplicate suppression, labels, no procedure logic |

All tests are currently skipped placeholders.

## Integration Contract

Before fusing, Module 05 checks:

| Field | Check |
|-------|-------|
| `frame_id` | Identical in both packets |
| `timestamp_s` | Consistent (within configured tolerance) |
| `target_track_id` | Identical in both packets |
| `status` | Not in `input.reject_statuses` |
| confidence values | Within `[0.0, 1.0]` |

Output guarantees:

- `ActivityEvent.activity_label` is from the configured label set (or `unknown`).
- `start_frame_id <= end_frame_id`; `frame_id` is the frame at which the activity was confirmed.
- One continuous activity produces one event.
- `conflicts` lists every resolved conflict; nothing is hidden.
- The event never contains a procedure verdict.

## Error / Failure Handling

| Failure | Behaviour |
|---------|-----------|
| Packets for different `frame_id` / `target_track_id` | Not fused; logged |
| Boundary packet missing | Fuse with Module 03 only if `allow_missing_boundary`; otherwise wait/skip |
| Upstream `ERROR` / `INVALID_INPUT` status | Packet rejected |
| Confidence outside `[0, 1]` | Packet rejected as `INVALID_INPUT` |
| Conflicting evidence | Configured policy applied; conflict recorded in event |
| Insufficient evidence | No event emitted (or `unknown` handled per config) |

## Current Limitations

- Activity vocabulary is a placeholder.
- Fusion method (rule-based vs. weighted) not yet chosen.
- Single operator / single target activity at a time.

## Future Improvements

- Learned fusion model trained on team-collected, labelled sessions.
- Concurrent activities of both hands.
- Uncertainty explanation shown to the operator.
