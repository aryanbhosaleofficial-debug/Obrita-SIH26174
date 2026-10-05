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
accidental staging. Unrelated GUI work changed concurrently during this task,
including the directory temporarily disappearing during the test rerun, then
returning with changes/new paths. HEAD and the index also changed independently.
This repair did not delete, move or restore GUI work or reset HEAD. No GUI path
is included in the prepared index. An unrelated unstaged deletion of
Obrita-SIH26174-main.zip was also observed; it is excluded from review staging
and was not performed here. Staging is a final-audit snapshot; external changes
can alter it later.

Review staging includes the outstanding Module 06 implementation/repair changes,
Module 03 producer/parity tests, the shared contract doc, and generated-artifact
untracking. Concurrent HEAD changes may already include some implementation/test
files; the classification manifest records the remaining changes. No commit is
created during the original repair task. The subsequent commit-verification
task commits the scoped repair; Git history is authoritative for its hash.

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

Implementation and repairs span 27 Module 06 files, two required Module 03
files, one shared schema file, and .gitignore hygiene. The final staged subset
depends on concurrent HEAD changes. Eleven generated-artifact deletions are
index-only cleanup. Any GUI modified/deleted/untracked files are unrelated work
and excluded. An exhaustive final-audit classification is written locally to
tests_tmp/module06/git-status-classification.tsv (ignored).
No model, screenshot, sample image or video is added to the index.

## Commit verification checkpoint

The outstanding repair is committed separately from unrelated GUI work. Before
committing, the tracked working tree matched the index and these checks passed:

| Command | Passed | Failed | Skipped | Errors |
| --- | ---: | ---: | ---: | ---: |
| `python -m pytest 06_pose_tracking/tests -q` | 130 | 0 | 0 | 0 |
| `python -m pytest 03_optimization/tests -q` | 104 | 0 | 28 | 0 |
| `python -m pytest -q` | 948 | 0 | 44 | 0 |

The inactive Module 03 handedness scaffold now documents where anatomical mirror
correction is implemented; no runtime logic was added to that scaffold.

To verify committed code independently, export the complete repository from
`git archive HEAD` into a new directory outside this working tree and run:

```text
python -m pytest 06_pose_tracking/tests -q
python -m pytest 03_optimization/tests/test_handedness_contract.py -q
python -m pytest -q
```

Run with PYTHONPATH unset; imports must resolve inside the export. A bare export
intentionally excludes .task models and sample media: the real-inference test
module explicitly skips until setup in models/README.md is performed. For the
asset-backed verification, supply only the documented two local .task bundles
and two optional sample JPGs, not Python files from the working tree. Compare
exported tracked source bytes with HEAD before and after tests. Diagnostics and
path-by-path staging classification remain under ignored
tests_tmp/module06/commit-verification. No production weights are committed.
