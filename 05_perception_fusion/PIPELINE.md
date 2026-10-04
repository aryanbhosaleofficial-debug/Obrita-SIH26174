# Module 05 — Perception Fusion Pipeline

## Overview

```text
 PREVIOUS: 03 Optimization                     PREVIOUS: 04 Boundary
 OptimizationOutputPacket                      BoundaryOutputPacket
            │                                           │
            └─────────────────────┬─────────────────────┘
                                  ▼
               ┌────────────────────────────────────┐
               │ 1. Packet Synchronization          │  input/fusion_synchronizer.py
               └─────────────────┬──────────────────┘
                                 ▼
               ┌────────────────────────────────────┐
               │ 2. Input Validation                │  input/packet_validator.py
               └─────────────────┬──────────────────┘
                                 ▼
               ┌────────────────────────────────────┐
               │ 3. Object Evidence                 │  evidence/object_evidence.py
               └─────────────────┬──────────────────┘
                                 ▼
               ┌────────────────────────────────────┐
               │ 4. Gesture Evidence                │  evidence/gesture_evidence.py
               └─────────────────┬──────────────────┘
                                 ▼
               ┌────────────────────────────────────┐
               │ 5. Interaction Evidence            │  evidence/interaction_evidence.py
               └─────────────────┬──────────────────┘
                                 ▼
               ┌────────────────────────────────────┐
               │ 6. Motion Evidence                 │  evidence/motion_evidence.py
               └─────────────────┬──────────────────┘
                                 ▼
               ┌────────────────────────────────────┐
               │ 7. Boundary / Contact Evidence     │  evidence/contact_evidence.py,
               │                                    │  evidence/boundary_evidence.py
               └─────────────────┬──────────────────┘
                                 ▼
               ┌────────────────────────────────────┐
               │ 8. Evidence Fusion                 │  fusion/evidence_fusion.py
               └─────────────────┬──────────────────┘
                                 ▼
               ┌────────────────────────────────────┐
               │ 9. Confidence Handling             │  fusion/confidence_fusion.py
               └─────────────────┬──────────────────┘
                                 ▼
               ┌────────────────────────────────────┐
               │ 10. Conflict Resolution            │  fusion/conflict_resolver.py
               └─────────────────┬──────────────────┘
                                 ▼
               ┌────────────────────────────────────┐
               │ 11. Temporal Confirmation          │  temporal/evidence_buffer.py,
               │                                    │  temporal/activity_confirmation.py
               └─────────────────┬──────────────────┘
                                 ▼
               ┌────────────────────────────────────┐
               │ 12. Activity Recognition           │  har/activity_recognizer.py,
               │                                    │  har/activity_labels.py
               └─────────────────┬──────────────────┘
                                 ▼
               ┌────────────────────────────────────┐
               │ 13. ActivityEvent Builder          │  har/activity_event_builder.py
               └─────────────────┬──────────────────┘
                                 ▼
                           ActivityEvent
                                 │
                                 ▼
          NEXT: Procedure FSM (procedure/fsm.py, step_validator.py, next_step.py)
```

## Interfaces

| Direction | Interface | Contract |
|-----------|-----------|----------|
| Previous | Module 03 | `OptimizationOutputPacket` (+ `ObjectFrame`, `SpatialFeaturePacket` pass-through) |
| Previous | Module 04 | `BoundaryOutputPacket` |
| Next | Procedure FSM | `ActivityEvent` |

## Stages

### 1. Packet Synchronization
- **Purpose:** Combine only packets describing the same frame and operator.
- **Input:** Both upstream packets.
- **Processing:** Match by `frame_id` and `target_track_id`; check timestamp consistency.
- **Output:** Packet pair.
- **Failure condition:** No match → wait/skip per config; missing boundary handled per `allow_missing_boundary`.
- **Next component:** Input Validation.

### 2. Input Validation
- **Purpose:** Reject unusable packets.
- **Input:** Packet pair.
- **Processing:** Check `frame_id`, `timestamp_s`, `target_track_id`, `status`, confidence range.
- **Output:** Validated pair.
- **Failure condition:** Any check fails → `INVALID_INPUT`, logged.
- **Next component:** Object Evidence.

### 3. Object Evidence
- **Purpose:** Which object is involved.
- **Input:** `ObjectFrame` (pass-through).
- **Processing:** Target object class, stability, confidence → evidence item.
- **Output:** Object evidence.
- **Failure condition:** No stable target → evidence marked missing.
- **Next component:** Gesture Evidence.

### 4. Gesture Evidence
- **Purpose:** Gesture contribution.
- **Input:** `GestureResult`.
- **Processing:** Use confirmed gestures as strong evidence; unconfirmed as weak.
- **Output:** Gesture evidence.
- **Failure condition:** `unknown` → evidence missing.
- **Next component:** Interaction Evidence.

### 5. Interaction Evidence
- **Purpose:** Hand-object interaction contribution.
- **Input:** `InteractionCandidate`s for the target object.
- **Processing:** Map `InteractionState` + confidence.
- **Output:** Interaction evidence.
- **Failure condition:** No candidate → evidence missing.
- **Next component:** Motion Evidence.

### 6. Motion Evidence
- **Purpose:** Movement contribution.
- **Input:** `MotionFeatures`.
- **Processing:** Rack-relative motion summary.
- **Output:** Motion evidence.
- **Failure condition:** No motion features → evidence missing.
- **Next component:** Boundary / Contact Evidence.

### 7. Boundary / Contact Evidence
- **Purpose:** Independent boundary-based contribution.
- **Input:** `BoundaryOutputPacket`.
- **Processing:** Confirmed `BoundaryState`, `hand_contact`, `crosscheck_agrees`.
- **Output:** Boundary and contact evidence.
- **Failure condition:** Packet missing / `quality_ok == False` → evidence missing or weak.
- **Next component:** Evidence Fusion.

### 8. Evidence Fusion
- **Purpose:** Score candidate activities.
- **Input:** All evidence items.
- **Processing:** Configured fusion method with config weights.
- **Output:** Per-activity candidate scores.
- **Failure condition:** All evidence missing → no candidate.
- **Next component:** Confidence Handling.

### 9. Confidence Handling
- **Purpose:** Combined confidence per candidate.
- **Input:** Candidate scores + evidence confidences.
- **Processing:** Treat missing evidence as unknown, not negative.
- **Output:** Candidate confidences in `[0, 1]`.
- **Failure condition:** Below `min_event_confidence` → candidate dropped.
- **Next component:** Conflict Resolution.

### 10. Conflict Resolution
- **Purpose:** Handle disagreement between Module 03 and Module 04.
- **Input:** Candidates + evidence.
- **Processing:** Apply configured policy; record each conflict.
- **Output:** Resolved candidate + conflict list.
- **Failure condition:** Unresolvable → candidate marked uncertain / dropped per policy.
- **Next component:** Temporal Confirmation.

### 11. Temporal Confirmation
- **Purpose:** Avoid flicker and duplicate events.
- **Input:** Resolved candidates over a window.
- **Processing:** N-of-M confirmation; activity start/end tracking.
- **Output:** Confirmed activity with start/end `frame_id`.
- **Failure condition:** Not confirmed → no event.
- **Next component:** Activity Recognition.

### 12. Activity Recognition
- **Purpose:** Final activity label.
- **Input:** Confirmed activity evidence.
- **Processing:** Map to configured label set.
- **Output:** Label + confidence.
- **Failure condition:** Insufficient evidence → `unknown` / no event per config.
- **Next component:** ActivityEvent Builder.

### 13. ActivityEvent Builder
- **Purpose:** Publish the module contract.
- **Input:** Label, confidence, frames, evidence summary, conflicts.
- **Processing:** Assemble shared `ActivityEvent`.
- **Output:** `ActivityEvent`.
- **Failure condition:** Contract violation → `ERROR`.
- **Next component:** Procedure FSM.
