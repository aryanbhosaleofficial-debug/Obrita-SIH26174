# Local hand model assets

The active default in `configs/optimization.yaml` is `models/hand_landmarker.task`.
Supply the genuine compatible MediaPipe Hand Landmarker Tasks bundle before real
inference, or pass `--hand-model <local-path>` to `scripts/run_fusion.py`.
No runtime download is performed; missing enabled assets are startup errors.

The optional body helper uses
`06_pose_tracking/models/pose_landmarker_lite.task`, configured by the existing
helper YAML, or `--pose-model <local-path>`. It is disabled by default in the
milestone. See [helper model setup](../06_pose_tracking/models/README.md).

Earlier reports describe local smoke-tested bundles; those are historical
verification records, not proof that models are installed in this checkout.
The repair audit found neither production bundle. Model-free tests inject
inference backends and are not real inference verification. All `.task` files
remain Git-ignored.
