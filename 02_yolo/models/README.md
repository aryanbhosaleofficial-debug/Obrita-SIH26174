# YOLO Model Weights

Place local YOLO weight files here (for example `<name>.pt` or `<name>.onnx`).

- Weight files are **not committed** (`*.pt`, `*.onnx`, `*.engine` are in `.gitignore`).
  Share them through the team's agreed offline channel.
- `configs/yolo.yaml` -> `detector.model_path` points to the file relative to the
  YAML file's directory, e.g. `../02_yolo/models/experiment_objects.pt`.
  Constructor and CLI paths are relative to the current directory.
- The pipeline must **never** download a model automatically. If the file is missing,
  Module 02 must fail with a clear error.

The configured experiment weights are absent. Supply them locally and replace
null placeholder IDs in `configs/classes.yaml` with the exact weight ID/name map.
Startup rejects mismatches; there is no generic downloaded-model fallback.
Supported formats are `.pt` and `.onnx`; ONNX requires a preinstalled runtime.

Use trusted team checkpoints: framework-required `.pt` deserialization stays
inside Ultralytics. The loader is not an untrusted-file sandbox. The optional
offline smoke uses temporary random weights and provides no accuracy measurements.

## Model record (fill in for each model used)

| Field | Value |
|-------|-------|
| File name | TBD |
| Architecture / variant | TBD |
| Classes (must match `configs/classes.yaml`) | TBD |
| Input size | TBD |
| Training data (source, size) | TBD — only record measured facts |
| Evaluation results | TBD — only record measured results, with the evaluation data used |
| Date / author | TBD |
