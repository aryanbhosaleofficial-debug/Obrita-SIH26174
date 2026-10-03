# ORBITA Task 4 Verification

## Existing implementation

- `models/bottleneck_network.py` consumes Task 2 tensors shaped `(batch, time, 74)` and performs temporal mean/max pooling, input projection, Bottleneck 1, explicit ReLU, Bottleneck 2, and a configurable classification head.
- `training/trainer.py` uses `torch.optim.Adam` only for parameter updates and stores model/optimizer state in checkpoints.
- `training/dataset.py` consumes structured per-person sequence samples and provides session-based splitting.
- Task 2 and Task 3 keep Human 1/Human 2 histories independent before model input.
- The pipeline uses only the current completed sequence window for inference; no future frames are used.

## Actual gaps found

- Model input shape and feature-schema compatibility were implicit rather than explicitly checked.
- Checkpoint save/load metadata did not include a schema/architecture contract, and load support was absent.
- A single-session split reused that session in both train and validation, which could leak temporal data.

## Files changed

- `orbita_human_activity/models/bottleneck_network.py`
- `orbita_human_activity/training/dataset.py`
- `orbita_human_activity/training/trainer.py`
- `orbita_human_activity/tests/test_task4_training.py`
- `TASK4_VERIFICATION.md`

Tasks 1–3 and upstream `mediapipe/` were not modified.

## Architecture dimensions

- Task 2 feature schema: `2.0.0`, fixed `D=74`.
- Default sequence length: `T=30`.
- Input projection: `148 -> 74` after concatenated temporal mean/max pooling.
- Bottleneck 1: `74 -> 32`.
- ReLU: explicit `torch.nn.ReLU`.
- Bottleneck 2: `32 -> 16`.
- Classification head: `16 -> 6` by default; dimensions are constructor-configurable.
- Runtime checks reject incompatible feature dimensions, sequence lengths, masks, or schema versions.

## Optimizer configuration

- Optimizer: Adam (`torch.optim.Adam`).
- Default learning rate: `0.001` in the project configuration; smoke test uses `0.005`.
- Betas: `(0.9, 0.999)`.
- Epsilon: `1e-8`.
- Weight decay: `0.0001`.
- Adam is not part of the inference model graph.

## Tests passed/failed

- Focused Task 4 tests: **7/7 passed**.
- Full existing suite: **38/38 passed**.
- `python -m compileall -q orbita_human_activity`: **PASS**.
- No test failures.
- Checkpoint round-trip, optimizer state restoration, schema guard, sequence dimensions, ReLU, and session-disjoint split are covered by focused tests.

## Synthetic training status

The existing two-epoch Adam smoke training completed successfully and wrote `checkpoints/smoke_model.pt`. It uses generated sequences only and is software execution evidence, not model-performance evidence. No accuracy claim is made.

## Real-data training status

Not performed. No real labeled project dataset, recording-session annotations, or held-out evaluation data are available. A final HAR model must not be trained or scored from the synthetic fixtures.

## Remaining blockers

- Real labeled, session-partitioned project data is required for training and evaluation.
- `models/pose_landmarker.task` remains missing, so native MediaPipe inference is unavailable.
- The existing checkpoint is a synthetic smoke artifact, not a deployable trained model.
- Real-camera/live inference and real two-person sequence validation remain unexecuted.

TASK 4 STATUS: **READY**

Exact test counts: **7/7 focused Task 4 tests passed; 38/38 full-suite tests passed.**
