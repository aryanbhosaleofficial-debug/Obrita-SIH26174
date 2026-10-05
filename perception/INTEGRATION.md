# Authoritative architecture decision — ORBITA

Decision: restore the team decomposition. This supersedes the combined Module 01
architecture introduced by commit d281159. Inspection found its only active
consumers were examples/tests; numbered modules were still scaffolds.

Camera / FramePacket -> Module 01 FrameProcessor -> PreparedFrame
-> Module 02 YoloPipeline -> ObjectFrame
-> Module 03 OptimizationPipeline -> OptimizationOutputPacket
-> Module 04 boundary input validation -> team-owned boundary analysis
-> Module 05 HAR -> procedure FSM.

Module 03 now exposes `optimization.OptimizationSequence.process(ObjectFrame)`
for image-free temporal processing. The existing `OptimizationPipeline` remains
the spatial integration wrapper and composes the same sequence/stabilizer. Both
publish the same shared `OptimizationOutputPacket`; there is no alternate tracker
or packet adapter. See [Module 03's implemented contract](../03_optimization/README.md).

## Module 03 temporal evidence contract

`object_frame.detections` and `observations.detections` contain matching filtered
CURRENT observations, detached from the Module 02 input and enriched with local
continuity/stability. Raw detector confidence remains available there.
`stable_detections` contains frozen `TemporalDetection` evidence, with EMA
confidence and explicit `observed`, missing count, and first/last seen frame/time.
It includes confirmed states retained during short gaps. Held boxes must never
be treated as fresh observations or new interaction evidence.

`temporal_window` contains bounded frozen `TemporalFrame` snapshots, with all
active tentative/confirmed states, source frame/time, upstream status and missing
count before each processed frame. It owns no source images or packet references.
Source/session/dimensions are inherited from the containing packet and windows
clear on context changes. Counts account for raw, filtered and duplicate inputs;
the current count is `len(packet.object_frame.detections)`. Serialize with
`dataclasses.asdict`; derived `stable_detection_count` is a convenience property.

Confirmation uses consecutive accepted observations, then tolerates misses up to
the configured limit. Expiry occurs when that limit is exceeded. Low-confidence
and lost/predicted tracker boxes age state rather than refresh it. Exact duplicate
geometry/class/track observations count once; distinct tracker IDs remain distinct.
Untracked continuity uses conservative class-consistent IoU and restarts on
ambiguity. Temporal-only code never assigns semantic actions or boundaries.

The owner config's `stabilization` section retains `detection_min_frames`,
`max_missing_frames`, `ema_alpha`, IoU/time settings and adds confidence floor,
history size, explicit `ema` aggregation and a per-frame detection limit.
Invalid contracts raise before state changes; healthy zero-detection frames are
normal. Explicit reset clears counters as well as histories for deterministic
replay. Local keys must be scoped to a source/session AND optimizer run; automatic
time/size discontinuities continue allocating new keys within a run.

Module 04's receiving validator checks the new window/current/stable consistency,
presence flags, confidence and counts along with existing metadata and geometric
contracts. It still performs no segmentation. Warm-up/empty/held-only outputs
are consumable contracts with false quality and explicit reasons. ERROR and
INVALID_INPUT outputs are unusable. Do not bypass the actual receiver with an
adapter. `PerceptionChain` serializes stage calls; direct optimizer callers must
serialize process/reset themselves.

## Module 01 owns

Frame validation, metadata/order/session checks, copy-safe preprocessing and
restoration transforms; shared coordinate/identity/status/configuration
conventions and typed integration boundaries. Implementation: perception/.
01_perception_core points here; its old camera/orchestration plan is superseded.
Camera ownership remains external.

## Module 01 does NOT own

YOLO inference/tracking (02); hands/pose, live rack calibration, continuity and
interaction processing (03); boundary algorithms (04); HAR (05); FSM, GUI,
speech, recording or application orchestration. Reusable implementations move
to numbered owners. Compatibility modules re-export; they contain no algorithms.

## Input, output, next module

Input: shared.schemas.FramePacket, uint8 BGR/RGB original image, actual size,
source/session identity, increasing integral frame ID (including NumPy integers),
monotonic seconds. Output: shared.schemas.PreparedFrame retaining source packet,
prepared BGR image, reversible scale, structured diagnostics and timings.
Next module: Module 02 YoloPipeline.

ObjectFrame, SpatialFeaturePacket, OptimizationOutputPacket are authoritative
stage packets. Shared observation leaves are defined once in observations.py.
PerceptionFrameResult becomes a compatibility alias for Module 03's observation
payload, not a Module 01 output. Import-safe yolo, optimization and boundary
packages locate implementations inside existing numbered owner directories.
The external integration chain composes stages and contains no inference logic.

## Coordinate conventions

Model outputs are restored to original pixels before crossing module boundaries.
x/W,y/H are display coordinates only. Euclidean fallback uses x/diagonal,y/diagonal
with an explicit coordinate label. Rack and image-diagonal thresholds are separate.
Static manual calibration is usable but never claims current-frame verification.
Live marker calibration reports actual verification and invalidates on marker loss.

## Identity conventions

`ObjectFrame.reference_anchors` / `ReferenceAnchor` are retained legacy schema
fields for compatibility, not an implemented Module 02 anchor-extraction path.
Module 02 always publishes an empty list, including when rack objects are detected.
Module 03 owns reference interpretation/calibration and publishes the canonical
`ReferenceFrameInfo` via `SpatialFeaturePacket.reference_frame`. Its current manual
or ArUco transformer reads source pixels/configuration, not that legacy list.
An empty anchor list does not mean reference loss. Any future producer/consumer
of this reserved field requires an explicit integration decision; class role
metadata alone does not assign calibration to YOLO.

track_id is backend-provided; None is valid. continuity_key is session-local,
short-term continuity generated by Module 03. identity_persistent identifies
tracker-backed identity. Namespace keys by source/session. Ambiguous crossings
restart continuity. Handedness and MediaPipe array index are not identity keys.
Tracker IDs can be reused after a backend reset. Use source/session, continuity
keys and reset diagnostics for temporal state; a tracker integer is never a
globally permanent identity.

## Error/status conventions

Capability notices differ from runtime warnings. Optional missing scores,
disabled tracking and static calibration are notices. OK is usable processing;
NO_DETECTION is healthy empty output; DEGRADED means partial runtime loss;
ERROR/FAILED and INVALID_INPUT mean unusable stage output. Codes carry structured
details separately from display text. Unknown confidence stays None. Reliability
is serialized explicitly. Missing/malformed frames age histories; source/session/
resolution changes, resets or excessive time gaps require fresh histories. A new
source/session requires explicit reset; it is otherwise rejected. Resolution or
excessive time gaps automatically restart histories and tracking backends.

Reliability means healthy processing AND at least one currently observed,
confirmed object. It does not certify identity, calibration freshness, unambiguous
association, action correctness or physical contact. Inspect those explicit fields
for the intended downstream decision. Empty scenes are healthy but unreliable for
object-based temporal reasoning. Capability notices alone never lower status.

`ERROR` (alias `FAILED`, wire value `error`) means inference has no functioning
required observation path; one failed backend with a remaining usable path is
`DEGRADED`. Config/model startup incompatibilities raise `InitializationError`;
they are not converted into permanently degraded runtime output. A configured
reference lost at runtime degrades the frame; deliberately disabled reference is
a notice with explicit image-diagonal coordinates.

Serialize `dataclasses.asdict(OptimizationOutputPacket)` or the observation
payload's `to_dict()`. Both include reliability, notices, warning codes, reference
source/verification and nullable confidence. `confidence.final` is the minimum
available evidence components, not a probability; all unknown yields `None`.

## Configuration ownership

perception.yaml owns preprocessing only. yolo.yaml is the sole real detector
configuration and validates weights against classes.yaml. optimization.yaml owns
hands, reference, interaction and temporal settings. Integration profiles reference
these files. Mock data and demo thresholds are explicitly synthetic/configurable.

## Verification boundary

Execute FrameProcessor -> YoloPipeline -> OptimizationPipeline -> actual Module 04
input validator using real shared packets. Model-free tests inject synthetic
inference backends only; stage logic and packet conversion stay real. Boundary
segmentation, HAR and FSM are not replaced or claimed complete by this repair.

## Migration from the conflicting implementation

`perception.PerceptionPipeline` is a lazy compatibility wrapper around the SAME
`integration.chain.PerceptionChain`; it returns only Module 03's observations.
New consumers must use the real stage packets. `perception.detector`, hands,
geometry/interaction/stabilizer and mocks/visualization modules are re-exports
only. No alternate inference or optimization implementation lives in Module 01.

`PerceptionConfig` aliases shared `PipelineConfig`, an application aggregate.
`configs/perception.yaml` now accepts preprocessing only; use the demo/mock
profile with `PerceptionChain.from_yaml` to configure the complete chain.
`configs/perception_tracker.yaml` is retired; use `configs/yolo_tracker.yaml`.

Previously unconsumed scaffold leaves now alias canonical types:
`DetectedObject = Detection`, `HandLandmarks = HandObservation`,
`InteractionCandidate = InteractionPrimitive`, `RackReference = ReferenceFrameInfo`.
This intentionally changes their old scaffold constructors. Construct detection
geometry with `bbox=BoundingBox(...)`; `bbox_xyxy` is a read-only compatibility
view. Hands use `Point2D` original pixels and optional raw handedness. Interactions
use `InteractionType`, explicit indices/continuity/units and evidence components.
Use `SpatialFeaturePacket.reference_frame` for serialized provenance;
`rack_reference` is only a compatibility view. No active pre-repair consumer used
the scaffold constructors; repository searches and all real tests were checked.

The original `MotionFeatures`, skeleton, gesture, boundary and HAR schemas remain
for teammate development. Unpopulated optional fields are not evidence that those
algorithms ran. Original GUI, procedure/FSM and inactive numbered algorithms were
not replaced.
