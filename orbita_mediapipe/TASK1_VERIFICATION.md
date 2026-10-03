# ORBITA Task 1 Verification

## 1. Files changed

- `orbita_human_activity/schemas/spatial_types.py`
- `orbita_human_activity/spatial/coordinate_systems.py`
- `orbita_human_activity/spatial/calibration.py`
- `orbita_human_activity/features/orientation.py`
- `orbita_human_activity/pipeline/visualizer.py`
- `orbita_human_activity/tests/test_spatial_transforms.py`
- `orbita_human_activity/tests/test_feature_extraction.py`
- `orbita_human_activity/tests/test_task1_visualizer.py`
- `TASK1_VERIFICATION.md`

Upstream `mediapipe/` and Tasks 2–4 source were not modified.

## 2. Gaps found

- Unvalidated rack-relative transforms were labeled `RACK_RELATIVE_CALIBRATED`.
- Active-landmark selection could prefer nominal rack coordinates over MediaPipe World coordinates.
- Calibration input validation did not explicitly reject malformed or degenerate point sets.
- The visualizer had ASCII output and Matplotlib initialization, but no skeleton/trajectory rendering method.
- No 90°/180° orientation robustness or basic visualization test existed.

## 3. Fixes made

- Added `RACK_RELATIVE_UNVALIDATED` coordinate metadata.
- Kept MediaPipe World coordinates active unless rack coordinates are verified calibrated.
- Preserved timestamp, frame index, person ID, and coordinate-frame metadata.
- Added shape and collinearity validation to the calibration interface.
- Added basic Matplotlib 3D skeleton, centroid, and trajectory rendering.
- Added tests for unvalidated transforms, degenerate calibration, metadata, 90°/180° orientation, and visualization.
- Roll/Pitch/Yaw remains unavailable for 2D-only or unsupported/degenerate inputs.

## 4. Tests passed/failed

- Task 1 tests: **13/13 passed**.
- Full existing suite: **21/21 passed**.
- `python -m compileall -q orbita_human_activity`: **PASS**.
- No test failures.

These results use the verified Python 3.12.14 runtime from Phase 1. No real-camera, real-video, or microgravity result is claimed.

## 5. Ready for Task 2?

**Yes.** Task 1 source-level gaps addressed and relevant/full automated tests pass. Task 2 may consume the documented 3D frame and orientation outputs.

## 6. Remaining blocker

`models/pose_landmarker.task` is still missing. Native MediaPipe Pose Landmarker inference remains unavailable; only the tested synthetic/offline path is verified.

