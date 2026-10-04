# Local hand model assets

Place the compatible MediaPipe Hand Landmarker bundle at
`models/hand_landmarker.task`, as referenced by `configs/perception.yaml`.
Obtain it before offline deployment from the
[official model page](https://developers.google.com/edge/mediapipe/solutions/vision/hand_landmarker#models).
The module never downloads a model at runtime. `.task` files are git-ignored.

A local official bundle was downloaded for adapter smoke verification in this
workspace. It is not a committed deployment asset. The final experiment object
YOLO weights still belong in `02_yolo/models/experiment_objects.pt`; see
`perception/README.md` for configuration and integration.
