# Module 02 minor repair - integration owner notes

Classification: **INTEGRATION OWNER SIGN-OFF** for changes listed below.
No AGENTS.md/CODEOWNERS ownership prohibition was found in the repository or
applicable ancestors. This repair request authorizes the smallest necessary
config/documentation corrections; no integration algorithm was changed.

## M02-R01 - configuration alignment

Applied config correction: configs/yolo_tracker.yaml new_track_thresh 0.60 -> 0.50.
Tracking stays enabled, matching configs/yolo.yaml confidence_threshold=0.50 and
track_high_thresh=0.50. Module 02 rejects high/new thresholds above detector
confidence when tracking is enabled. Thresholds are not empirically optimized.
Integration profiles and class IDs are unchanged. Review this config correction
with the integration owner; it is implemented, not a pending unmade change request.

## M02-R03 - schema/integration documentation alignment

Conflict: optional ObjectFrame.reference_anchors and historical class/scaffold
comments suggested Module 02 anchor extraction; authoritative integration and
active Module 03 assign reference calibration to Module 03's manual/ArUco path.

Decision: retain ReferenceAnchor/reference_anchors for schema/import/wire
compatibility, with no new active producer. Module 02 always publishes []; the
field does not report visibility/calibration loss. Reference derivation/calibration
belongs to Module 03 and is published as SpatialFeaturePacket.reference_frame
(ReferenceFrameInfo). No semantic rack calibration was added to detection.

Affected alignment: shared/schemas/object_frame.py (comments/docstring only),
perception/INTEGRATION.md, configs/classes.yaml (comments only), historical Module
03 PIPELINE/DOD notices, Module 02 docs/deprecated scaffold notices. Field names,
types/defaults and serialized shapes are unchanged, so no consumer migration is
required. A regression executes actual Module 03 manual calibration with an empty
legacy anchor list. Any future producer/consumer of the reserved field needs a
new explicit schema/integration decision and consumer tests; none is introduced
in this repair. Integration/schema owner review covers the wording alignment.

## M02-R06 - existing script exception

scripts/run_yolo.py already delegates to yolo.cli.main and was committed in
e33b21b (Module 02). It is correct, used by README and verified with --help.
It is **unchanged by this repair**. Its historical Module 02 change in an
integration-owned directory requires integration-owner sign-off; retain the
working delegation rather than reverting it solely to shrink an old diff.

This note is review material only. No messages were sent to another owner and
no external sign-off is claimed.
