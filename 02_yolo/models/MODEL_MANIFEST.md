# Module 02 model manifest

Verified on **2026-10-05** from the actual current checkpoint. HAR.zip is **absent**; no archive was recreated or downloaded, and working weights were not overwritten.

| Field | Verified value |
|---|---|
| Filename | best.pt |
| Runtime path | 02_yolo/models/best.pt |
| Size | 6,249,770 bytes |
| SHA-256 | `b9ab5c71a5c4e0ed151d6e8001983e5e7d5a5995a73cc419d580da304f1c687d` |
| Architecture | Ultralytics DetectionModel / YOLOv8n; current pickle metadata identifies yolov8n.pt and C2f/SPPF/Detect layers |
| Classes | 0 lid; 1 main_box; 2 red_box; 3 yellow_box |
| Matching class map | 02_yolo/config/har_classes.yaml |
| Matching detector profile | 02_yolo/config/standalone.yaml |
| Expected historical source | HAR/best.pt inside the user-supplied 02_yolo/HAR.zip |
| Current provenance | Existing working checkpoint; digest agrees with the earlier migration audit. The absent archive prevents rechecking archive-member equality in this pass. |
| Metadata inspection | Static ZIP/pickletools inspection; no unpickling merely to inspect metadata. Real inference separately validates loading/class-map compatibility. |
| Git policy | Binary .pt files remain ignored by the root .gitignore; this manifest is source-controlled at freeze. No automatic binary commit. |

## Verified backup and restoration

A second physical copy was created and SHA-256 verified at:

```text
C:\Users\lalit\AppData\Local\ORBITA\ModelBackups\b9ab5c71a5c4e0ed151d6e8001983e5e7d5a5995a73cc419d580da304f1c687d\best.pt
```

This is a durable local backup outside the repository, **not a team-shared or off-machine backup**. The team must include the same digest-named artifact in its managed offline model bundle / backup storage; Git alone cannot restore the ignored weights. Distribute the manifest, class YAML, detector profile and checkpoint together. Do not substitute five-class weights.pt or another checkpoint under this filename.

Restore from the verified local backup without downloading:

```powershell
$modelBackup = 'C:\Users\lalit\AppData\Local\ORBITA\ModelBackups\b9ab5c71a5c4e0ed151d6e8001983e5e7d5a5995a73cc419d580da304f1c687d\best.pt'
Get-FileHash -LiteralPath $modelBackup -Algorithm SHA256
# Compare with the SHA-256 above before restoring a missing file.
Copy-Item -LiteralPath $modelBackup -Destination '02_yolo/models/best.pt'
Get-FileHash -LiteralPath '02_yolo/models/best.pt' -Algorithm SHA256
```

Keep a copy outside this computer for recovery from disk loss. A local checkpoint is a required runtime asset; absence produces InitializationError. Model extraction/inspection tools require the original HAR.zip and are optional historical setup tools. Runtime never downloads the archive, YOLO weights or Qwen model.
