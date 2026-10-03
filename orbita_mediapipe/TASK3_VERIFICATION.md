# ORBITA Task 3 Verification

## 1. Existing implementation reused

- `tracking/association.py`: 3D/2D spatial association, gating, and assignment.
- `tracking/identity_policy.py`: Human 1/Human 2 slot lifecycle policy.
- `tracking/tracker.py`: persistent track management and deletion.
- `schemas/tracking_types.py`: track state, IDs, pose history, hits, lost-frame uncertainty.
- `pipeline/pose_adapter.py`: up-to-two-person detector configuration and synthetic two-person input.
- `pipeline/orbita_pipeline.py`: per-person downstream feature/sequence processing.

## 2. Files changed

- `orbita_human_activity/schemas/tracking_types.py`
- `orbita_human_activity/tracking/association.py`
- `orbita_human_activity/tracking/identity_policy.py`
- `orbita_human_activity/tracking/tracker.py`
- `orbita_human_activity/pipeline/orbita_pipeline.py`
- `orbita_human_activity/tests/test_task3_tracking.py`
- `TASK3_VERIFICATION.md`

Task 1/2 implementation, Task 4 implementation, and upstream `mediapipe/` were not modified.

## 3. Actual gaps

- New-slot assignment could inherit detector-array order rather than a defined spatial policy.
- Missing hips could produce a fabricated zero 3D centroid for association/tracking.
- Assignment policy was not configurable through the tracker.
- Coasting tracks retained a stale pose and could be processed downstream as a new observation.
- No focused tests covered crossing, deletion/reuse, no-fabrication, or independent downstream histories.

## 4. Fixes

- Added configurable `SPATIAL_LEFT_RIGHT` (default) and `FIRST_COME_FIRST_SERVE` policies.
- New slots are spatially ordered; established identities are maintained by association, not detection-array order.
- Added shoulder-centroid fallback when hips are unavailable; if no valid centroid exists, no zero is fabricated.
- Added `last_observed_timestamp_ms` and clear it during misses.
- Prevented coasting/stale poses from creating new Task 2 feature or sequence samples.
- Added controlled synthetic tests for one/two people, reorder/crossing, movement, occlusion, reappearance, deletion/reuse, assignment, no-fabrication, and history isolation.

## 5. Tracking/identity policy

- Supports up to two active slots: `HUMAN_1` and `HUMAN_2`.
- Persistent IDs are track/slot IDs assigned after spatial-temporal association.
- State is exposed as `TENTATIVE`, `CONFIRMED`, `COASTING`, or `DELETED`, with hits, age, lost frames, and last observed timestamp.
- Human 1/Human 2 feature histories and temporal buffers remain keyed independently by `person_id`.
- This is short-term spatial-temporal tracking only. It is not biometric identity recognition or guaranteed long-term re-identification after deletion.

## 6. Tests passed/failed

- Focused Task 3 tests, including existing tracking tests: **10/10 passed**.
- Full existing suite: **34/34 passed**.
- `python -m compileall -q orbita_human_activity`: **PASS**.
- No test failures.

All Task 3 scenarios are controlled synthetic/unit tests; no tracking performance claim is made.

## 7. Real-video status

Not executed. No real two-person video is available, and `models/pose_landmarker.task` remains absent. Native MediaPipe multi-person inference is therefore unverified.

## 8. Remaining blockers

- Missing `models/pose_landmarker.task` blocks native Pose Landmarker execution.
- No real two-person recording is available for real-video identity/occlusion validation.
- Long-term identity recognition/re-identification remains intentionally out of scope.

TASK 3 STATUS: **READY**

Exact test count: **34/34 full-suite tests passed**; **10/10 focused Task 3 tests passed**.

