# Module 04 final P1 repair — final independent review

Scope: only tight object boxes and tolerated dropped frame IDs. The earlier merge
and major repair were preserved. This report supersedes their padding and
frame-gap descriptions; their test counts remain historical.

## A. Files changed

| File | Reason / behavior changed |
|---|---|
| `04_boundary/config.py` | Python default padding ratio is 0.1. |
| `configs/boundary.yaml` | Shipped padding ratio is 0.1; missing-count and motion-unit comments clarified. All other numeric settings preserved from this task's starting state. |
| `04_boundary/boundary_pipeline.py` | Reset semantic classifier only above missing-frame tolerance; pass the accepted original frame ID to the classifier. |
| `04_boundary/temporal/boundary_change.py` | Bounded frame-ID history alongside centroids; motion thresholds use displacement divided by elapsed source frames. Reset clears both histories. |
| `04_boundary/tests/test_final_p1.py` | 14 parametrized cases for defaults, continuous/dropped motion, tolerance boundaries, time-gap reset, duplicate/backwards input rejection. |
| `tests/test_boundary_runtime_integration.py` | 16 new real Module 03 integration cases; ROI-fill/border fixtures now fill/follow the actual padded ROI. Their rejection assertions remain intact. |
| `04_boundary/README.md` | Authoritative defaults, units, gap rules, clipping and upstream-quality limitation. |
| `04_boundary/PIPELINE.md` | Padded ROI and dropped-frame behavior documented. |
| `04_boundary/DEFINITION_OF_DONE.md` | Reviewed-blocker acceptance checks added; independent freeze approval remains pending. |
| `04_boundary/FINAL_P1_REPORT.md` | This review record. |

SHA256 comparison against the 494-file task-start snapshot found only the eight
existing files above changed, plus the new regression file and this report.
No project files were deleted. Modules 01–03/05/06, shared contracts, GUI, FSM,
root README and perception integration documentation were unchanged during this
task. Earlier uncommitted work remains in the working tree.

## B. Tight-box fix

Previously Python and YAML used zero relative padding. An exact object crop could
appear uniform or ROI-filling and correctly fail the existing conservative gate.

Both defaults now use `padding_ratio=0.1`. The integrated bbox gets 10% of its
largest dimension on each side. Existing ROI extraction floors/ceils and clamps
crop coordinates to image dimensions; it rejects non-intersecting/empty crops.
That already-correct clamping implementation was preserved. Requested padding may
extend outside the image; actual slicing and published contours remain inside.

Real canonical FramePacket + OptimizationSequence output tests detect the actual
51-by-51 object with exact boxes, in both polarities, at the center, all four edges
and two corners. They assert geometry, centroid, area, bounds, target/frame/time
identity, shared packet type and no source/upstream mutation.

No segmentation, border-rejection or confidence algorithms were relaxed.
A ROI-fill fixture was expanded from the old zero-padding ROI to the new padded
ROI so it still tests actual contamination rather than a valid tight object.

## C. Dropped-frame fix

Missing count remains `current_frame_id - previous_frame_id - 1`.
The classifier now preserves history when this count is at most
`max_missing_frames` (default 2) and resets above it.

Motion steps use `centroid_displacement / (next_frame_id - previous_frame_id)`.
This retains the existing pixels-per-original-source-frame thresholds without
introducing an assumed FPS. Net-displacement/path-length coherence still uses
the raw geometric path. Only actual valid processed frames vote; dropped IDs do
not fabricate votes. The new frame-ID deque is bounded by motion_min_frames and
cleared by reset alongside centroids.

Timestamp ordering and max_time_gap_s reset are unchanged. Duplicate/backwards IDs
and nonincreasing timestamps still return INVALID_INPUT without modifying state.
Invalid geometry/upstream rejection, target/resolution changes and explicit reset
retain existing reset rules. Source/session changes still require explicit reset.

Integration limitation preserved: Module 03 degrades packets when its own source
frames are missing, and Module 04 honors that quality gate. The real integration
tests therefore drop valid packets between Module 03 and Module 04. Direct
Module 04 tests independently cover accepted source-frame ID gaps. No Module 03
behavior or quality policy was changed.

## D. New regression tests

Thirty added parametrized cases:

- Consistent Python, shipped YAML and runtime padding defaults.
- Exact object boxes: bright/dark polarity at seven positions (14 cases).
- Continuous stationary IDs and repeated one/two missing IDs (3 cases).
- MOVING with regular and irregular tolerated gaps (2 cases).
- Slow motion with gaps remains below MOVING threshold (1 case).
- Inclusive missing tolerance, excess gap reset and zero tolerance (3 cases).
- Large timestamp gap still resets despite acceptable ID gap (1 case).
- Duplicate ID, backwards ID and duplicate timestamp preserve rejection/state (3 cases).
- Real Module 03 packets delivered to Module 04 with repeated drops, stationary
  and moving (2 cases).

Existing geometry-quality, contact/state, explicit-reset, offline CLI and
read-only ownership regressions remain in the executed suite.

## E. Test results

Interpreter: repository `.venv/Scripts/python.exe`.
Each pytest invocation used `-p no:cacheprovider` and a distinct `--basetemp`
under `C:\Users\lalit\AppData\Local\Temp\orbita_module04_final_p1_14badcb3d1eb78`.
The parent was explicitly created before final fixture-dependent runs.

| Final command target | Passed | Failed | Skipped | Errors |
|---|---:|---:|---:|---:|
| `python -m compileall -q 04_boundary shared` | n/a (exit 0) | 0 | n/a | 0 |
| `pytest -q 04_boundary/tests` | 146 | 0 | 5 | 0 |
| `pytest -q tests/test_optimization_to_boundary.py` | 10 | 0 | 0 | 0 |
| `pytest -q tests/test_boundary_runtime_integration.py` | 38 | 0 | 0 | 0 |
| `pytest -q 03_optimization/tests` | 96 | 0 | 28 | 0 |
| `pytest -q` | 809 | 0 | 68 | 0 |
| Focused P1 + runtime integration tests | 52 | 0 | 0 | 0 |

Ruff check passed for all five touched Python files. Full suite completed in
18.42 seconds; this is test runtime, not a live-video performance benchmark.
Thirty new passing cases relative to the reviewed 779-pass starting suite.
Skipped cases are separate from passes. Module 04's five skips remain genuinely
deferred HSV, contour association/resampling, rack rotation and cross-check.

Earlier attempts, for transparency:

| Attempt | Passed | Failed | Skipped | Errors | Explanation |
|---|---:|---:|---:|---:|---|
| Pre-fix focused reproducer | 3 | 23 | 0 | 0 | Reproduced blockers; 26 deselected. |
| First patched focused suite | 50 | 2 | 0 | 0 | Upstream missing-frame policy rejected evidence; corrected integration fixture to model delivery drops without altering upstream behavior. |
| First Module 04 suite | 126 | 0 | 5 | 20 | Missing parent of requested pytest basetemp, WinError 3. Parent created and suite rerun successfully. |
| First Module 03 suite | 87 | 0 | 28 | 9 | Same temporary-directory setup error; successful rerun above. |

No product failures or test errors remain in final runs.

## F. Regression status and Git audit

Verified by the passing suites:

- Dark/light polarity and actual-object geometry.
- Uniform/empty/noisy ROI rejection and padded-ROI fill/border rejection.
- Rejected quality publishes zero confidence and no strong contact.
- STATIONARY/MOVING/CONTACT and N-of-M confirmation.
- Existing SEPARATING tests unchanged and passing; no redesign.
- Explicit stream reset, input-order validation and source ownership.
- Offline deterministic core and local standalone CLI.

No network/model/framework dependency was added; requirements were unchanged.
Rack orientation, cross-check, hand masking, Module 05 consumer and shared
source/session schema requests remain outside this task.

Executed `git status --short`, `git diff --stat`, `git diff --check` and reviewed
the diffs. The accumulated earlier merge/major-repair work remains uncommitted:
32 tracked files changed, 1687 insertions and 1093 deletions at final P1 audit;
untracked files are not included in that stat. This is not the size of this
task's surgical patch. Task-start hash audit isolates the files listed in A.
Diff check exited 0 with no whitespace errors; Git emits existing LF-to-CRLF
conversion notices. `git diff --cached --name-only` is empty: nothing staged.

Recovery ZIP remains untracked/unstaged and unchanged:
`Obrita-SIH26174-main.zip`, SHA256
`B37D9163C790879FEB0DCE618502F241BAC01F0F72F02F591EF98EF3DF91FEFE`.

Cleanup is a non-blocking environment restriction. Verified temporary targets:

- `C:\Users\lalit\AppData\Local\Temp\orbita_module04_recovery_21e8f08af76d41cf97b769e3e3959256`
- `C:\Users\lalit\AppData\Local\Temp\orbita_module04_repair_30bde71a6d45b`
- `C:\Users\lalit\AppData\Local\Temp\orbita_module04_final_p1_14badcb3d1eb78`

All resolved under TEMP with no reparse points. Automatic approval review rejected
native PowerShell recursive removal with reason “blocked by policy”; these folders
remain outside the repository. No alternative deletion mechanism was used.

## G. Final status

**READY FOR FINAL INDEPENDENT REVIEW**

Both scoped blockers pass regression and full-suite validation. Freeze approval
belongs to the independent reviewer. This remains an unbenchmarked SIH prototype,
with no flight-certification or real microgravity-validation claim.
