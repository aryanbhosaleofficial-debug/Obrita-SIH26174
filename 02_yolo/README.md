# Module 02 — YOLO

Module 02 owns detection, optional backend tracking and detector class validation.
The active stage is `yolo.pipeline.YoloPipeline`: `PreparedFrame -> ObjectFrame`.
Implementation files remain here; `yolo/` is only an import-safe package locator.

`inference/detector.py` contains the isolated local Ultralytics adapter and
`ObjectDetector` protocol. `inference/class_map.py` checks local weight metadata
against `configs/classes.yaml`. `configs/yolo.yaml` is the sole real detector
configuration; `configs/yolo_tracker.yaml` configures its optional tracker.

Inference sees prepared BGR pixels. Published boxes are restored to ORIGINAL
source pixels with source/session/frame/time metadata. `track_id=None` is valid;
no substitute tracker ID is generated here. Backend errors become structured
runtime failures; healthy empty output is `NO_DETECTION`.

Short-term spatial continuity, evidence confirmation, hands, calibration and
interaction reasoning belong to Module 03. The older stability/reference/etc.
files in this folder are inactive planning placeholders, not alternate stages.
`PIPELINE.md` and `DEFINITION_OF_DONE.md` retain historical planning detail where
not yet implemented; the current boundary above and the shared integration
contract take precedence.

The team must supply trained `models/experiment_objects.pt` and the exact class
map before a real demonstration. No cloud or runtime asset download is permitted.
See [setup and execution](../perception/README.md),
[authoritative contracts](../perception/INTEGRATION.md) and
[verification evidence](../perception/VERIFICATION.md).
