# Module 06 model assets

Local MediaPipe Tasks bundles. They are git-ignored (`*.task`), so install them
once per machine with network, then run offline. The code never downloads.

| File | Default location | Official download (one-time setup) | SHA-256 of the copy verified here |
| --- | --- | --- | --- |
| `pose_landmarker_lite.task` (5,777,746 bytes) | `06_pose_tracking/models/` | https://storage.googleapis.com/mediapipe-models/pose_landmarker/pose_landmarker_lite/float16/latest/pose_landmarker_lite.task | `59929e1d1ee95287735ddd833b19cf4ac46d29bc7afddbbf6753c459690d574a` |
| `hand_landmarker.task` (7,819,105 bytes) | `models/` (repo root, shared with Module 03) | https://storage.googleapis.com/mediapipe-models/hand_landmarker/hand_landmarker/float16/latest/hand_landmarker.task | `fbc2a30080c3c557093b5ddfc334698132eb341044ccee322ccf8bcf3607cde1` |

The `latest` URLs can change over time. Record the checksum of the files you deploy.

`pose_landmarker_full.task` / `pose_landmarker_heavy.task` are drop-in
alternatives. Download one and set `pose_model_path` in
`config/pose_tracking.yaml`. They are slower and were not measured here.
