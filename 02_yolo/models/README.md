# Local Module 02 models

The Modules 01–05 project profile (`configs/yolo.yaml`) expects
`02_yolo/models/experiment_objects.pt`. Supply genuine trained local weights, or
set `--model <local .pt/.onnx>` in the milestone runner. The single-image YOLO
command also accepts `--weights`. Paths in YAML resolve relative to that YAML;
CLI paths resolve relative to the current working directory.

The trained model's complete class ID/name mapping must exactly match a local
classes YAML. The project `configs/classes.yaml` still contains unset IDs because
the real taxonomy has not been supplied. Complete it from your model's actual
metadata, or use `--classes <matching-local-yaml>`; do not invent class IDs.

Earlier [MODEL_MANIFEST.md](MODEL_MANIFEST.md) and standalone reports describe a
historical `best.pt` checkpoint and a four-class profile
(`02_yolo/config/standalone.yaml`, `har_classes.yaml`). That checkpoint is absent
in this checkout. No production `.pt`/`.onnx` was found, and the local repository
ZIP contains no weights. Historical backup paths are not runtime defaults.
If you restore the genuine checkpoint, select its matching model/profile/classes
explicitly; do not rename incompatible weights or blend class taxonomies.

Runtime requires existing local weights, disables Ultralytics online checks and
automatic dependency installation, and validates local trackers with ReID off.
The SIH wrapper disables optional localhost semantic inference by default.
The separate standalone Qwen/voice demonstration remains outside the milestone.

Model binaries are Git-ignored. No production asset was fabricated or downloaded
during this repair. See [milestone repair report](../../MODULES_01_05_REPAIR.md)
for actual commands, synthetic verification and deployment requirements.
