# Module 06 P2/P3 repair review

The current architecture is preserved. Required P2 findings are repaired:

- Nearby LEFT/RIGHT label flicker cannot cross-blend EMA: compare candidate
  centroids with a previous-frame snapshot of both live tracks. If the opposite
  track is closer, reset that labelled track and its streak. Jump resets, stale
  expiry, loss holds and normal smoothing remain. No physical identity guarantee
  is claimed for ambiguous crossings.
- HandObservation.handedness is anatomical after mirror correction. Module 03
  now corrects mirrored Tasks labels at the producer. Module 06 already corrects
  before its shared adapter. mirrored_input is metadata only; consumers must not
  swap again. Existing title-case values and unknown=None API are retained.
- Only Module 06 implementation/repair files and the required Module 03/shared
  compatibility changes are prepared for review. Unrelated GUI work is excluded.

Safe P3 repairs: VIDEO timestamps are reserved before either inference task;
sync uses PALM_INDICES; local source/camera opening precedes model initialization;
mirror-display reflects pixels/draw positions before readable text. Core frames
and published coordinates/handedness never change for a display-only mirror.

## Regression coverage

- Nearby x=256/320 two-hand label swaps, either candidate order, then recovery
- Normal nearby two-hand EMA and expired opposite-track handling
- Both anatomical sides with mirrored/unmirrored Module 03/06 producer parity
- Shared contract documentation and mirror metadata retention
- Pose or hand failure after accepting a VIDEO timestamp, followed by sub-ms frames
- Missing local source/unavailable camera before model loading
- Readable status text and reflected skeletal positions without packet mutation

## Reproducible setup and hygiene

Models and optional positive-inference sample images are local, ignored setup
assets. Exact official version-1 URLs, SHA-256 hashes, expected paths and setup
commands are in [models/README.md](models/README.md). No runtime/test download was
introduced. YOLO production weights are not part of this repair.

Eleven old generated Module 06 pytest video/image/JSONL/YAML artifacts under
tests_tmp were accidentally tracked despite the existing ignore rule. They are
removed from the Git index only; local files remain. New test/runtime artifacts
stay under ignored tests_tmp. No screenshot_*.png files were present initially;
the full suite's existing GUI smoke test then generated 12 root screenshots.
The targeted /screenshot_*.png ignore rule preserves these locally and prevents
accidental staging. Unrelated GUI files were excluded from staging. The GUI
directory temporarily disappeared during the final test rerun, then returned;
this repair did not delete, move or restore it. No GUI path is included in the
prepared index. An unrelated unstaged deletion of Obrita-SIH26174-main.zip was
also observed; it is excluded from review staging and was not performed here.

Review staging includes the previously uncommitted Module 06 implementation,
this targeted repair, Module 03 producer/parity tests, the shared contract doc,
and the generated-artifact untracking. No commit is created by this task.

Duplicate Module 03 + Module 06 hand inference is deferred as an optional
optimization. Physical scene acceptance, calibration and model accuracy limits
remain documented in DEFINITION_OF_DONE.md; this is readiness for final code
review, not flight certification or a microgravity performance claim.

## Repair verification

| Command | Passed | Failed | Skipped | Errors |
| --- | ---: | ---: | ---: | ---: |
| `python -m pytest 06_pose_tracking/tests -q --tb=short` | 130 | 0 | 0 | 0 |
| `python -m pytest -q 03_optimization/tests tests/perception/test_adapters.py --tb=short` | 119 | 0 | 28 | 0 |
| `python -m pytest -q --tb=short` | 943 | 0 | 44 | 0 |

An earlier full-suite run passed 944 with 44 skips while the unrelated GUI
smoke test was present. The final rerun after that directory disappeared passed
943 with 44 skips; this repair did not remove it.

Root imports and scoped compileall passed. The synthetic composed runner
processed 36 frames with zero pipeline errors. The standalone real-model video
runner processed three frames and exported mirrored-display MP4 and JSONL
headlessly. This verifies file input/inference/export, not physical live scenes.
The ten added Module 06 tests and five Module 03 tests use injected inference
components; real sample inference remains separately covered by five existing
Module 06 model tests. No missing-model initialization exception is suppressed.

Prepared source/config/doc changes: 27 Module 06 files, two required Module 03
files, one shared schema file, and .gitignore hygiene. Eleven generated-artifact
deletions are index-only cleanup. The 18 GUI files seen at the earlier audit were
unrelated existing work and were never staged; they returned before the final
audit. No model, screenshot, sample image or video is added to the index.
