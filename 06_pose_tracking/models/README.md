# Module 06 local assets and setup

Runtime loads local MediaPipe Tasks bundles only. Missing models are reported;
no runtime function or test downloads them. Genuine version-1 bundles were
fetched from Google's official storage during the original Module 06 implementation
as an explicit setup step; the P2/P3 repair reused those local assets. They are
ignored by Git (`*.task`) and remain local, shared with the
existing Module 03 helper where applicable.

| Default local path | Bytes | SHA-256 verified during setup |
| --- | --- | --- |
| `06_pose_tracking/models/pose_landmarker_lite.task` | 5,777,746 | `59929e1d1ee95287735ddd833b19cf4ac46d29bc7afddbbf6753c459690d574a` |
| `models/hand_landmarker.task` | 7,819,105 | `fbc2a30080c3c557093b5ddfc334698132eb341044ccee322ccf8bcf3607cde1` |

Official sources:

- [Pose Lite version 1](https://storage.googleapis.com/mediapipe-models/pose_landmarker/pose_landmarker_lite/float16/1/pose_landmarker_lite.task)
- [Hand version 1](https://storage.googleapis.com/mediapipe-models/hand_landmarker/hand_landmarker/float16/1/hand_landmarker.task)
- [MediaPipe Tasks Python API guide](https://developers.google.com/edge/mediapipe/solutions/vision/hand_landmarker/python)

One-time setup on another machine (PowerShell, from repository root):

```powershell
New-Item -ItemType Directory -Force -Path 06_pose_tracking/models,models,tests_tmp/module06
Invoke-WebRequest -Uri 'https://storage.googleapis.com/mediapipe-models/pose_landmarker/pose_landmarker_lite/float16/1/pose_landmarker_lite.task' -OutFile 06_pose_tracking/models/pose_landmarker_lite.task
Invoke-WebRequest -Uri 'https://storage.googleapis.com/mediapipe-models/hand_landmarker/hand_landmarker/float16/1/hand_landmarker.task' -OutFile models/hand_landmarker.task
Get-FileHash 06_pose_tracking/models/pose_landmarker_lite.task,models/hand_landmarker.task -Algorithm SHA256
```

Alternatively provide existing local models with CLI --pose-model / --hand-model
or edit the YAML paths. YAML paths are relative to that config file. Full/heavy
pose alternatives are not benchmarked here. Do not substitute random bytes or
rename unrelated model weights as .task bundles.

Optional positive-inference test fixtures (also setup-only, never committed):

```powershell
Invoke-WebRequest -Uri 'https://storage.googleapis.com/mediapipe-assets/pose.jpg' -OutFile tests_tmp/module06/pose.jpg
Invoke-WebRequest -Uri 'https://storage.googleapis.com/mediapipe-assets/right_hands.jpg' -OutFile tests_tmp/module06/right_hands.jpg
python -m pytest -q 06_pose_tracking/tests/test_pose_real_models.py
```

`SIH_MODULE06_SAMPLE_DIR` optionally points to a different local sample folder.
The pose fixture has SHA-256
`c8a830ed683c0276d713dd5aeda28f415f10cd6291972084a40d0d8b934ed62b`;
the hand fixture has
`4b5134daa4cb60465535239535f9f74c2842aba3aa5fd30bf04ef5678f93d87f`.
Google's `right_hands.jpg` contains TWO RIGHT HANDS, not one left and one right.
The tracker keeps both geometries, labels the strongest RIGHT and the duplicate
UNKNOWN, and preserves both raw labels. With fresh Tasks instances, the model
reports Right on the unmirrored fixture and Left on its mirror; input_mirrored
correction preserves the anatomical interpretation in both cases. This does not
verify all real-person/camera handedness scenarios or model accuracy.

The real full Modules 01–06 composition still needs the user's local YOLO
experiment_objects.pt; no YOLO asset was fetched or fabricated in this task.
