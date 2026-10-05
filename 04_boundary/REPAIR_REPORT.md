# Module 04 — Targeted Repair After Independent Review

**Code repair verdict: READY FOR INDEPENDENT RE-REVIEW.**
This is a handoff for a different reviewer, not an implementer declaration that
Module 04 is frozen. Requested cleanup remains policy-blocked, as recorded below.

Repository: `C:\Users\lalit\OneDrive\Desktop\Aryan\Project\SIH26174\Obrita-SIH26174`;
branch `v1`. Work repaired the already-merged implementation in place;
no archive extraction or re-merge was performed.

## A. Files changed

The repair-start SHA-256 snapshot contained 492 tracked/untracked project files.
Compared with that snapshot: **26 existing files modified, two new files added,
no file removed**. No pre-existing work was reset or discarded. The index change
unstaged only the recovery ZIP; its source contents remain identical.

| File | Reason | Behavior changed |
|---|---|---|
| `04_boundary/boundary_pipeline.py` | Gate masks/quality before trusted output; integrate supported temporal states and explicit stream/reference handling. | Both-polarity selection, safe contact/confidence/state, new-stream rejection until reset; preserves canonical receiver. |
| `04_boundary/config.py` | Validate the reviewed segmentation/temporal controls and every owned key. | Unknown/unsupported-enabled settings fail; aliases validated; no hidden feature enablement. |
| `04_boundary/segmentation/foreground_segmenter.py` | Generate both threshold polarities without repeating thresholding. | Binary/inverse candidate masks; Canny silhouettes receive the same quality checks. |
| `04_boundary/segmentation/segmentation_quality.py` | Added lightweight explainable mask assessment. | Information/occupancy/separability/dominance/fill consistency score and rejection reasons. |
| `04_boundary/contour/contour_validator.py` | Add ROI-local border analysis. | Report sides/fraction/bbox contamination; one-edge clipping is permitted. |
| `04_boundary/quality/boundary_quality_gate.py` | Prevent solidity from dominating confidence. | Segmentation-weighted score; rejection zeroes public confidence. |
| `04_boundary/output/boundary_packet_builder.py` | Enforce shared-packet safety invariants. | Quality-failed packets suppress contact, confidence and confirmed state; populate confirmation fields. |
| `04_boundary/temporal/boundary_change.py` | Implement deterministic state candidates using valid evidence. | STATIONARY/MOVING/CONTACT/SEPARATING, motion coherence and bounded identified-hand release anchor. |
| `04_boundary/temporal/confirmation.py` | Replace future placeholder with bounded N-of-M confirmation. | Only current non-UNKNOWN candidate confirms; matching vote count and reset are explicit. |
| `04_boundary/temporal/boundary_tracker.py` | Correct ownership docstring only. | No tracker behavior change; classifier owns states. |
| `04_boundary/standalone_cli.py` | Expose caller rack validity. | --rack-valid assertion unblocks configured gate without calibration. |
| `04_boundary/tests/test_segmentation.py` | Replace implemented-area scaffolds and add P0 cases. | Both polarities, uniform scenes, seeded/bimodal noise, ROI fill/outline, morphology, ownership, Canny. |
| `04_boundary/tests/test_contours.py` | Replace implemented-area scaffolds. | Offsets/area and border rejection/one-edge acceptance; two genuine future skips retained. |
| `04_boundary/tests/test_boundary_packet.py` | Replace implemented-area scaffolds. | Metadata/type/quality reasons and rejected-confidence/contact/state invariants. |
| `04_boundary/tests/test_boundary_tracking.py` | Replace state/tracking scaffolds. | Stationary/moving, N-of-M, spike rejection, target/gap/reset, invalid quality, bounded deterministic replay. |
| `04_boundary/tests/test_contact.py` | Replace implemented-area scaffolds. | Confirmed contact/separation, low-quality suppression, missing/unidentified hand and no-motion rejection. |
| `04_boundary/tests/test_boundary_config.py` | Validate new keys and safety behavior. | Ranges, unknown nested keys, unsupported flags, aliases, effective/read-only YAML and confidence warm-up. |
| `04_boundary/tests/test_boundary_runtime.py` | Verify explicit standalone reference interface. | Valid assertion permits quality; malformed assertion rejects safely without fabricated orientation. |
| `04_boundary/tests/test_boundary_cli.py` | Verify CLI rack assertion. | Shipped YAML rejects without assertion and passes with it; orientation remains None. |
| `tests/test_boundary_runtime_integration.py` | Exercise reviewed defects through real Module 03. | All P0 scenarios, metadata/ownership, hand suppression, all four states and source/session reset. |
| `configs/boundary.yaml` | Replace misleading enabled placeholders with explicit demo settings. | Validated segmentation/state defaults; cross-check/include_hands disabled; rack requirement preserved. |
| `04_boundary/README.md` | Make contract/algorithm/status/config docs accurate. | Implemented versus deferred features, exact semantics, scores, limits and test commands. |
| `04_boundary/PIPELINE.md` | Document repaired runtime order. | Quality gating precedes public evidence and state votes. |
| `04_boundary/DEFINITION_OF_DONE.md` | Track targeted repair and review boundary. | Implemented items checked; independent freezing decision and future capabilities remain unchecked. |
| `04_boundary/MERGE_REPORT.md` | Retain original audit as historical evidence. | Added supersession note/link; original merge decisions/results not rewritten. |
| `README.md` | Minimal Module 04-specific integration claim correction. | Supported states described; no unrelated project code changes. |
| `perception/INTEGRATION.md` | Minimal authoritative boundary-status documentation correction. | Supported confirmed states documented; 01-03 orchestrator and all contracts unchanged. |
| `04_boundary/REPAIR_REPORT.md` | Added independent re-review handoff. | This file-by-file behavior/verification/deferred/cleanup report. |

Shared schemas/enums, requirements and Modules 01/02/03/05/06/GUI/FSM implementation
files remain byte-identical. The only edits in perception/root documentation
correct the Module 04 boundary behavior; no neighbor logic/interface was changed.
No new dependency, network/model path or alternative packet was introduced.

## B. P0 repair

### Polarity

Threshold is evaluated once; its complement supplies the inverse candidate.
Both threshold/adaptive polarities pass identical quality checks. Canny outlines
are filled and assessed as silhouettes. Fixed bright-object assumptions no
longer select the light background around a dark object.

Selection uses valid segmentation score, with deterministic candidate ordering.
Area is only a tie-breaker within an already-valid component, never a reason to
prefer the ROI background.

### Border contamination and occupancy

ROI-local contour analysis records touched sides, fraction of points near the
border and whether the contour bbox spans the ROI. The bbox-spanning contour is
rejected unconditionally. Otherwise too many sides plus the configured
border-point fraction rejects contamination. One normal clipped edge is allowed
and explicitly tested.

The foreground fraction must be within configured bounds. A contour covering
almost the whole ROI is also rejected. Dominant-component and filled-contour
consistency checks reject fragmented masks, holes and background outlines.

### Low-information and noise rejection

Raw grayscale standard deviation is checked before trusting any segmentation.
Uniform/low-information ROIs return NO_DETECTION with no contour, zero confidence
and explicit reasons.

Between-class variance / total grayscale variance measures foreground/background
separability. Gaussian-like intensity noise cannot gain confidence from a convex
outline alone. Bimodal/fragmented noise additionally encounters component and
border checks. Tests cover five deterministic random seeds, bimodal noise and
all reviewed real-Module-03 cases. This is conservative prototype behavior, not
a guarantee for every possible noisy/cluttered scene.

### Confidence

Segmentation score is:
`min(separability, component_dominance, contour_fill_fraction, 1-border_fraction)`.

Final score is:
`segmentation_score * (0.50 + 0.25*solidity + 0.25*continuity_score)`.

Continuity is zero initially, then the minimum of current and previous accepted
segmentation score. There is no hand/contact confidence boost. Solidity can no
longer override failed occupancy, border, information or coherence checks.

Every rejected public-quality packet has **confidence=0, hand_contact=false,
contact_confidence=0, UNKNOWN/unconfirmed state and confirmed_frames=0**.
Failed masks do not publish contours. A later rack/upstream/confidence rejection
may retain geometry only as rejected diagnostic evidence.

If the only rejection is the confidence threshold, already-valid segmentation
may warm bounded geometry continuity, avoiding permanent startup rejection
under stricter thresholds. It does not cast semantic votes or publish contact;
rack/upstream/segmentation failures do not use that warm-up path.

## C. State classifier

Only complete quality-accepted geometry enters the state classifier.

| Candidate | Rule |
|---|---|
| STATIONARY | At least motion_min_frames centroids; every recent step <= stationary_tolerance_px |
| MOVING | Every recent step >= moving_threshold_px, with net displacement/path length >= min_motion_coherence |
| CONTACT | Quality-valid geometry plus near-boundary proxy >= contact_min_confidence |
| SEPARATING | Prior confirmed CONTACT, same identified hand, release beyond contact range, distance increased from contact anchor and coherent MOVING evidence |
| UNKNOWN | Warm-up, dead-zone/ambiguous or unconfirmed current candidate |

CONTACT has precedence. Separation is a bounded transition within confirmation_m
released valid frames after confirmed contact; missing/unidentified/replaced
hands or stationary release cannot confirm SEPARATING. The integrated path
reuses Module 03's hand continuity key when available.

A current non-UNKNOWN candidate must appear N times in the last M valid
candidate frames. Default N=2/M=3. The packet reports that confirmed candidate,
state_confirmed=true and the matching vote count (bounded by M). Otherwise
UNKNOWN/false/0 is published. Old state confirmation is not carried across a new
unconfirmed candidate.

All semantic histories are bounded and clear on invalid/absent geometry, missing
frame IDs, target/resolution changes, excessive time gaps and reset. Geometry
retention alone cannot preserve a confirmed CONTACT through bad frames.
A source/session change now returns INVALID_INPUT without mutation until the
caller explicitly resets, matching upstream stream ownership.

Motion is Euclidean **image-plane** displacement for a fixed-camera demo, not a
physical gravity direction or rack rotation. CONTACT/SEPARATING describe image
proximity evidence, not proof of physical activity. ROTATING remains unsupported
and orientation_deg_rack remains None.

## D. Configuration changes

Current `configs/boundary.yaml` explicitly records these **prototype** defaults:

```yaml
roi:
  padding_ratio: 0.0
  padding_px: 0
  include_hands: false
preprocessing:
  blur_kernel: 3
  illumination: {method: none, params: {}}
segmentation:
  method: threshold
  params: {}
  min_roi_stddev: 5.0
  min_foreground_fraction: 0.01
  max_foreground_fraction: 0.90
  min_component_dominance: 0.80
  min_contour_fill_fraction: 0.85
  min_separability: 0.80
contour:
  border_margin_px: 1
  max_border_sides: 2
  max_border_point_fraction: 0.35
features:
  contact_distance_px: 20.0
  contact_min_confidence: 0.5
temporal:
  history_frames: 20
  max_missing_frames: 2
  max_time_gap_s: 1.0
  motion_min_frames: 3
  stationary_tolerance_px: 1.0
  moving_threshold_px: 2.0
  min_motion_coherence: 0.8
  separation_distance_increase_px: 2.0
  confirmation_n: 2
  confirmation_m: 3
  rotation_threshold_deg: null
crosscheck:
  enabled: false
quality:
  require_valid_rack_reference: true
  min_confidence: 0.35
```

Morphology defaults are open=0/close=0/iterations=1/min-component-area=0;
contour area/perimeter limits are min=20/max=None/min-perimeter=0.
Connectivity remains 8; start normalization/differential remain true;
require_optimization_quality remains true. Null placeholders are replaced by
explicit equivalent demo defaults, except deliberately disabled unsupported
flags. No previously tuned nonnull threshold was discarded.

Unknown section, nested and parameter keys now fail clearly. Enabling
crosscheck/include_hands, non-none illumination, HSV, nonnull resampling/rotation
settings or non-8 connectivity raises an unsupported-feature error. Empty
reserved HSV/illumination data can remain for compatibility, not active support.
Conflicting legacy/canonical aliases fail rather than silently winning.

Legacy confirmation_min_hits/window and stationary_tolerance map to the real
n/m/stationary_tolerance_px settings. Null blur explicitly means default 3;
use 0 or 1 to disable it. Threshold invert sets initial candidate order but both
polarities still get assessed.

Standalone process/process_detections now accept explicit rack_valid: bool,
default false; CLI exposes --rack-valid. This is a caller assertion, not invented
calibration. The integrated path retains canonical Module 03 reference validity.
A valid assertion unblocks the shipped rack gate without populating orientation.

Error API compatibility is retained: programmer packet-contract mismatches raise
BoundaryInputError; malformed raw inputs/order/new-stream operational errors
return INVALID_INPUT packets. The documented distinction avoids breaking the
established receiver.

## E. New tests

The required reviewed scenarios have real assertions:

| Scenario | Verified expected result |
|---|---|
| White object on black | Valid contour at object, not crop rectangle |
| Black object on white | Same valid object geometry; inverse candidate selected |
| Uniform grey/black/white | NO_DETECTION, no high confidence |
| Seeded random intensity noise | Rejected, zero confidence/contact |
| Bimodal fragmented noise | Rejected |
| ROI-filling foreground | Occupancy rejection |
| Border-following mask/scene | Border rejection even when solid |
| Legitimate object touching one edge | Not automatically rejected |
| Low-quality geometry + nearby hand | Zero confidence/contact; no confirmed state |
| Stationary over valid window | Confirmed STATIONARY |
| Consistent translating object | Confirmed MOVING |
| Single centroid spike | No confirmed MOVING |
| Contact over valid window | Confirmed CONTACT |
| Confirmed contact then moving/released hand | Confirmed SEPARATING |
| Missing/unidentified hand or stationary release | No SEPARATING |
| N-of-M with intervening candidates | Correct confirmation/count/window expiry |
| Invalid geometry, gap, target change, reset | Old state votes do not leak |
| Long execution and replay | Bounded buffers, deterministic confirmed outputs |
| Standalone/CLI reference assertion | Required quality gate honors explicit bool; no orientation invented |
| Unknown config keys and unsupported true flags | Clear errors |
| Strict confidence startup | Trusted geometry warms; rejected frame publishes no contact/state |
| Real Module 03 -> Module 04 | All reviewed P0 cases and all four supported states; preserved metadata/type/identity/ownership |
| New source/session | Explicit reset required, prior context unchanged on rejection |

Only five named future tests remain skipped: HSV, multi-contour target
association, resampling, rack-relative rotation and optimization cross-check.
Previously implemented areas are no longer covered solely by skipped scaffolds.

## F. Test results

Interpreter: `R/.venv/Scripts/python.exe`, R = repository above.
Every pytest command used `-q -p no:cacheprovider` and a fresh
`--basetemp T/<suffix>`, where:
`T=C:\Users\lalit\AppData\Local\Temp\orbita_module04_repair_30bde71a6d45b`.

These selections overlap; do not sum their passed counts.

| Command selection / basetemp suffix | Passed | Failed | Skipped | Errors |
|---|---:|---:|---:|---:|
| python -m pytest -q -p no:cacheprovider --basetemp T/final_module04 04_boundary/tests | 132 | 0 | 5 | 0 |
| python -m pytest -q -p no:cacheprovider --basetemp T/final_contracts tests/test_packet_contracts.py | 24 | 0 | 0 | 0 |
| python -m pytest -q -p no:cacheprovider --basetemp T/final_receiver tests/test_optimization_to_boundary.py | 10 | 0 | 0 | 0 |
| python -m pytest -q -p no:cacheprovider --basetemp T/final_runtime tests/test_boundary_runtime_integration.py | 22 | 0 | 0 | 0 |
| python -m pytest -q -p no:cacheprovider --basetemp T/final_module03 03_optimization/tests | 96 | 0 | 28 | 0 |
| python -m pytest -q -p no:cacheprovider --basetemp T/final_all | 779 | 0 | 68 | 0 |

Intermediate repair runs were also executed, before later tests/format cleanup:

| Selection / suffix | Passed | Failed | Skipped | Errors | Resolution |
|---|---:|---:|---:|---:|---|
| 04_boundary/tests, first_module04 | 100 | 3 | 5 | 0 | Three new tests used a nonexistent blur_kernel constructor keyword; corrected to existing BoundaryConfig API, assertions retained. |
| 04_boundary/tests tests/test_boundary_runtime_integration.py, second_module04 | 148 | 0 | 5 | 0 | Targeted implementation/integration passed. |
| Same combined selection, third_module04 | 152 | 0 | 5 | 0 | Additional transitions/config warm-up passed. |

Other executed commands/results:
- `python -m compileall -q 04_boundary shared`: exit 0.
- Exact importlib numbered-package smoke: succeeded.
- Ruff check on the 19 repaired Python paths: all checks passed; format check:
  19 files already formatted.
- Network-blocked/model-free confirmed-state subprocess smoke: passed. Existing
  pytest offline smoke blocks socket connect/create_connection and verifies no
  model/GUI import; passed in Module 04 suite.
- Executable illegal numbered-import scan: no matches.
- Actual conflict-marker scan: no matches.
- BoundaryOutputPacket/BoundaryState definitions: one authoritative shared class/
  enum each.
- Git diff --check: clean, exit 0.

Full repository changed from pre-review **697 passed/83 skipped** to
**779 passed/68 skipped**, with no failures/errors. Fifteen implemented-area
Module 04 skips became real tests; five genuine future skips remain. Other
repository skips are reported honestly as unavailable features, not passes.

## G. Deferred items

- Rack-relative orientation and ROTATING; orientation remains None, no camera-up
  approximation.
- Optimization cross-check and hand-expanded ROI, explicitly disabled/rejected
  when enabled.
- HSV, illumination correction, contour association and resampling. Published
  contours remain dense original pixels; shared schema unchanged.
- Module 04 -> Module 05 consumer verification unavailable because Module 05 is
  not implemented. It is not treated as a Module 04 failure.
- source_id/session_id additions to BoundaryOutputPacket: future centralized
  shared-schema request; no schema change in this repair.
- Physical contact/action correctness, flight/microgravity validation and measured
  performance/accuracy: not claimed.
- Cleanup of the temporary recovery/test directories and generated smoke file:
  blocked by automatic approval review (below).

## H. Git status

Executed `git status --short`, `git diff --stat`, `git diff --check`;
also inspected changes and compared the repair-start hashes.

The working tree contains the previous merge's uncommitted changes plus this
repair. Cumulative tracked diff:
**32 files changed, 1652 insertions(+), 1094 deletions(-)**.
Ordinary diff --stat excludes untracked implementations/tests/reports. It is not
the size of this repair alone; section A distinguishes the 26 changed baseline
files and two new files.

Status shows M for 32 tracked paths from cumulative merge/repair, and untracked
Module 04 implementations/tests/reports and root integration test. Existing
pre-merge untracked files were retained. The original archive is now
`?? Obrita-SIH26174-main.zip` after authorized
`git restore --staged -- Obrita-SIH26174-main.zip`; no source deletion.
The staged diff is empty. No commit/reset/clean/checkout was performed.

Archive SHA-256 remains:
`B37D9163C790879FEB0DCE618502F241BAC01F0F72F02F591EF98EF3DF91FEFE`.

No accidental out-of-scope implementation edits or tracked deletions occurred;
466 other baseline files remained identical. The only outside-owner changes are
the requested boundary YAML and runtime integration tests, plus minimal
Module 04-specific root/authoritative integration documentation corrections.

Cleanup evidence:
- Verified temp paths resolve beneath Windows Temp and have no reparse-point
  attributes; no ZIP extraction was redone.
- `outputs/events/boundary_smoke.jsonl` was generated by the prior merge and is
  ignored/untracked, not a fixture.
- Automatic approval review rejected native literal-path removal of both
  directories and of that single output file, stating **“blocked by policy.”**
- No alternate deletion mechanism or permission escalation bypassed the rejection.

Artifacts still present:
`C:\Users\lalit\AppData\Local\Temp\orbita_module04_recovery_21e8f08af76d41cf97b769e3e3959256`,
`C:\Users\lalit\AppData\Local\Temp\orbita_module04_repair_30bde71a6d45b`,
and `R/outputs/events/boundary_smoke.jsonl`.

## I. Repair verdict

**READY FOR INDEPENDENT RE-REVIEW**

The reviewed P0/P1 runtime defects have regression coverage through standalone
and real Module 03 inputs. Supported states, quality-safe output and strict
configuration now operate deterministically and offline; all required tests pass.
The next reviewer should assess the explicit prototype heuristics/limits and
decide whether to freeze. No freeze approval is claimed here.

Requested cleanup is still outstanding solely because automatic approval review
blocked the removals; that environmental restriction is separate from the passing
runtime/tests and is not represented as completed cleanup.
