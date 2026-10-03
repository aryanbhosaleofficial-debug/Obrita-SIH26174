# Native MediaPipe Verification

- Expected model path: configured default `models/pose_landmarker.task`; the resolver now locates the existing repository asset at `mediapipe/models/pose_landmarker_heavy.task`.
- Model asset status: **PRESENT**. No model was downloaded, generated, or duplicated.
- Native initialization status: **PASS** with the installed MediaPipe wheel and the existing Heavy asset. Verified `is_real_detector=True` and `num_poses=2`.
- One-frame result: **PASS**. Local repository image `mediapipe/calculators/image/testdata/dino_quality_80.jpg` returned 1 native pose with 33 normalized and 33 world landmarks.
- Video result: not executed; no project video is available. The repository video fixture is unrelated upstream object-detection data.
- Webcam result: not executed; no webcam validation was requested or evidenced.
- Two-person configuration: `num_poses=2`, preserved in the existing runner and CLI.
- Synthetic fallback: preserved. When native initialization is unavailable, the runner reports `is_real_detector=False` and `Synthetic/Offline Pose Generator`.
- Tests passed: targeted native initialization/inference check and source compilation passed. The prior full suite remains **40/40 passed**; it was not rerun because this change was limited to asset resolution.
- Environment note: a normal repo-root import can shadow the installed MediaPipe wheel with the checked-out upstream source tree, which lacks the wheel’s native DLL. Native verification was run with installed-wheel precedence; upstream source was not modified.

Changed files:

- `orbita_human_activity/pipeline/pose_adapter.py`
- `orbita_human_activity/run_pipeline.py`
- `NATIVE_MEDIAPIPE_VERIFICATION.md`

NATIVE MEDIAPIPE STATUS: **READY**
