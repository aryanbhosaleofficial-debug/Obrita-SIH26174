# Data

Local data used for offline development and testing. Large/raw media is **not** committed
(see `.gitignore`); only folder placeholders and small curated samples are.

| Folder | Contents | Committed? |
|--------|----------|------------|
| `raw/` | Raw captures from the demo camera. | No (ignored) |
| `videos/` | Recorded demo videos used for offline replay (`configs/camera.yaml` → `source.type: video`). | No (ignored) |
| `annotations/` | Labels for detection / activity evaluation. Format to be decided by the team and documented here. | Yes (small files only) |
| `samples/` | Small sample frames/clips used by tests. Keep files small. | Yes (small files only) |

## Rules

- Record the capture conditions (camera, lighting, setup) for every dataset added.
- Do not commit personal data of people who have not agreed to it.
- Do not report dataset size or accuracy numbers anywhere unless they were actually measured on this data.
- All paths in configs must be relative to the repository root.
