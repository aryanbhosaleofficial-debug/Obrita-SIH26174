# YOLO Model Weights

Place local YOLO weight files here (for example `<name>.pt` or `<name>.onnx`).

- Weight files are **not committed** (`*.pt`, `*.onnx`, `*.engine` are in `.gitignore`).
  Share them through the team's agreed offline channel.
- `configs/yolo.yaml` → `model.path` must point to the file, relative to the repository root,
  e.g. `02_yolo/models/<name>.pt`.
- The pipeline must **never** download a model automatically. If the file is missing,
  Module 02 must fail with a clear error.

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
