# Local Module 02 models

`best.pt` is the local prototype YOLOv8n detection checkpoint extracted explicitly from `../HAR.zip` by `python 02_yolo/tools/extract_har_model.py` (run from the repository root). It is Git-ignored, so distribute it with the standalone directory or supply `--weights` separately. The extraction script verifies the audited size and SHA-256 and does not execute pickle code. Model metadata was inspected statically before subsequent real inference verification.

The active HAR class map is `../config/har_classes.yaml`: 0 lid, 1 main_box, 2 red_box, 3 yellow_box. The matching detector profile is `../config/standalone.yaml`. Paths in detector YAML are relative to its directory. Existing `configs/yolo.yaml` remains a separate project profile with its original class expectations; it does not automatically switch models.

`HAR/weights.pt` is a different YOLO26n checkpoint with five classes (HAR, Lid, main_box, red_box, yellow_box). Prototype main.py does not use it. It remains in the archive and is not needed for the default demo. Do not rename it to best.pt or combine its class IDs with the four-class map.

Runtime never downloads models. Install dependencies and explicitly obtain trusted local weights before offline operation. ONNX is supported by the reviewed adapter when onnxruntime is separately installed. Qwen weights belong to Ollama's local model store, not this directory. Both supplied YOLO checkpoints carry Ultralytics AGPL license metadata.

See [the Module 02 README](../README.md) and [implementation report](../UPDATE_REPORT.md) for setup, verification and limitations.
