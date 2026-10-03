# ORBITA Four-Task Integration

## Exact pipeline path

`MediaPipePoseLandmarkerRunner` (native Pose Landmarker when the asset exists, otherwise explicit synthetic fallback)
→ `MultiPersonTracker` (`HUMAN_1` / `HUMAN_2`)
→ `PersonPose3D` active 3D coordinates
→ `TemporalFeatureBuilder` (Task 2 schema `2.0.0`, `D=74`)
→ `TemporalSequenceManager` (per-person causal windows)
→ `OrbitaBottleneckHAR` (input projection → Bottleneck 1 → ReLU → Bottleneck 2 → classification head)
→ `PredictionResult` and JSONL output.

The same tracked person-specific poses are forwarded to `TrajectoryVisualizer3D`.

## Files changed

- `orbita_human_activity/pipeline/orbita_pipeline.py`
- `orbita_human_activity/tests/test_four_task_integration.py`
- `FOUR_TASK_INTEGRATION.md`

No Task 1–4 functional redesign and no upstream `mediapipe/` changes.

## Integration tests

- Controlled synthetic four-task path: **2/2 passed**.
- Verifies persistent Human 1/Human 2 IDs, independent metadata histories, ordered timestamps, schema `2.0.0`, `D=74`, causal first inference window, explicit synthetic mode, and visualization pose handoff.
- Existing synthetic pipeline smoke test: **1/1 passed**.
- `python -m compileall -q orbita_human_activity`: **PASS**.

## Full test count

**40/40 tests passed.** No failures.

## Synthetic integration result

**PASS.** Thirty-five synthetic frames completed the full path and produced per-person feature/prediction output. Synthetic fallback is distinguishable through `pose_runner.is_real_detector == False` and the runtime message identifying `Synthetic/Offline Pose Generator`.

Missing landmarks and invalid 3D orientation remain represented by Task 2 masks/status fields; no fabricated observations are introduced. Schema and dimension mismatches are rejected at the Task 2 → Task 4 interface.

## Remaining native MediaPipe blocker

`models/pose_landmarker.task` is missing. Native MediaPipe Pose Landmarker inference, including native camera/video execution, remains unverified.

## Remaining real-data blocker

No real labeled project recordings or held-out session-partitioned evaluation data are available. No real-camera or real-world HAR performance claim is made.

FOUR-TASK INTEGRATION: **PASS**
