# Module 06 processing and integration

```text
PreparedFrame (source FramePacket retained)
 -> validate type, upstream acceptance, reference matrix, source/session and ordering
 -> load local MediaPipe Tasks models once (Pose + Hand, synchronous VIDEO)
 -> normalized backend positions -> original source pixels
 -> visibility/presence validity masks; confident anatomical handedness or UNKNOWN
 -> compare hand centroids with both previous live tracks; reset ambiguous label association
 -> EMA per valid joint, bounded hold, streak/reset/loss handling
 -> camera normalized XY + optional existing image-to-rack homography
 -> padded/clamped source-pixel hand box
 -> PoseFrame (identity, metadata, explicit coordinates, validity, measured timings)
 -> downstream interaction / HAR (outside Module 06)
```

`TrackingIntegration` consumes the existing `MilestoneResult`: retained
`upstream.prepared`, synchronized ActivityEvent/BoundaryOutputPacket/ObjectFrame,
and `upstream.optimization.spatial.reference_frame`. It does not interpret the
activity or detect a workspace. `pipeline_runner` composes this adapter with the
existing MilestonePipeline for both real sources and explicit inference fakes.

Unavailable reference -> normalized_image. Malformed valid reference ->
INVALID_INPUT before inference/state advancement. Invalid upstream images skip
inference. Per-frame backend failure -> empty ERROR packet and clear EMA; the
next frame can recover. Missing models are explicit startup errors; one-model
availability is DEGRADED. No runtime network access or automatic asset downloads.

Core tracking is headless. Optional visualization draws on a detached original
source image and skips invalid joints. --mirror-display transforms that rendered
copy only; --mirror explicitly changes inference input and handedness correction.
The display mirror is applied before readable text, with reflected draw positions.
Shared HandObservation handedness is anatomical after correction; mirrored_input
is provenance only. Module 03 and Module 06 follow this same producer contract.

All existing compatibility imports and Module 01–05 implementations remain.
See README.md for exact contracts, runner commands and limitations.
