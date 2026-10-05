# Module 06 verification checklist

Recorded in this repair on branch v1, 2026-10-05. Checked items are backed by
an automated test or an actual run. Unchecked items are not claimed complete.
This is a SIH prototype, not flight-certified or microgravity-validated software.

## Implemented and verified

- [x] Existing numbered package, root locator, legacy helpers and shared contracts inspected
- [x] One authoritative PoseFrame / HandPose / Landmark contract; compatibility preserved
- [x] MediaPipe Tasks API verified in the actual Python 3.14.7 / MediaPipe 1.0.1 environment
- [x] Genuine local version-1 pose and hand bundles loaded; hashes recorded in models/README.md
- [x] 33 pose joints and 21 joints per detected hand; two geometries retained
- [x] Tasks handedness correction verified on unmirrored/mirrored Google hand fixture
- [x] Low pose visibility / supplied presence explicitly invalidates joints
- [x] Uncertain/duplicate handedness is UNKNOWN; missing scores remain None
- [x] Source frame/time/source/session/dimensions and copied metadata retained
- [x] EMA, invalid-joint recovery, loss holds/expiry, streak counts and reset tested
- [x] Pixel, normalized-camera and optional rack coordinates remain explicit
- [x] Existing rack homography consumed; 0/90/180-degree geometry equivalence tested
- [x] Padded/clamped hand boxes and safe geometry with invalid joints tested
- [x] Core runs headlessly; optional drawing skips invalid/extreme landmarks
- [x] Mirror preview leaves inference coordinates unchanged
- [x] Invalid source images skip inference; per-frame failure clears stale state and recovers
- [x] Model startup failure is explicit; partial availability is DEGRADED
- [x] Real Module 05 identity checked via TrackingIntegration; no frame invented in ActivityEvent
- [x] Module 03 handedness producer aligned with the shared anatomical contract; other Module 01–05 implementations unchanged; no new HAR/FSM logic
- [x] Synthetic Modules 01–06 run processes 36 frames with zero pipeline errors
- [x] Standalone live camera: 30 frames, 10 fresh pose observations, zero error/invalid packets
- [x] Stored real-model pose sample and two-hand sample inference succeed
- [x] Local 12-frame video (repeated public hand fixture): hand observations on all 12 frames;
      JSONL and annotated MP4 written, zero error/invalid packets
- [x] q/Esc model/window cleanup verified with injected display events
- [x] Source/video EOF and failure cleanup covered by tests
- [x] No runtime Python network client/downloader in Module 06; tests block Python sockets
- [x] Model binaries and downloaded sample/diagnostic artifacts are Git-ignored

## Final verification results

| Command | Result |
| --- | --- |
| `python -m pytest 06_pose_tracking/tests -q --tb=short` | 130 passed, 0 failed, 0 skipped, 0 errors |
| `python -m pytest -q 03_optimization/tests tests/perception/test_adapters.py --tb=short` | 119 passed, 0 failed, 28 skipped, 0 errors |
| `python -m pytest -q --tb=short` | 943 passed, 0 failed, 44 skipped, 0 errors |
| `python -m compileall -q 06_pose_tracking pose_tracking` | PASS |
| `python -c "import pose_tracking; from pose_tracking import PoseHandTracker, TrackingIntegration; print('Module 06 import OK')"` | PASS |
| `python -m 06_pose_tracking --help` | PASS |
| `python -m pose_tracking.pipeline_runner --synthetic --max-frames 36 --output tests_tmp/module06/repair-pipeline.jsonl` | PASS, 36 frames, zero pipeline errors |
| `python -m 06_pose_tracking --source tests_tmp/module06/hand-clip.mp4 --no-show --max-frames 3 --mirror-display --output tests_tmp/module06/repair-preview.mp4 --jsonl tests_tmp/module06/repair-video.jsonl` | PASS, 3 frames, local models, readable mirrored-overlay export |
| `python -m 06_pose_tracking --source 0 --no-show --max-frames 30 --jsonl tests_tmp/module06/camera-result.jsonl` | PASS, actual local camera |
| `python -m 06_pose_tracking --source tests_tmp/module06/hand-clip.mp4 --no-show --max-frames 12 --output tests_tmp/module06/annotated-hand-clip.mp4 --jsonl tests_tmp/module06/video-result.jsonl` | PASS, actual local models + video reader/writer |
| Real `pose_tracking.pipeline_runner` with local video | Clear startup failure: missing `02_yolo/models/experiment_objects.pt` |

The earlier full-suite run, with the unrelated GUI smoke test still present,
passed 944 tests with 44 skips. After the GUI directory disappeared from the
workspace independently of this repair, the final rerun passed 943 with 44 skips.
The full suite's 44 skips belong to optional/asset-dependent checks outside the
successful Module 06 run. No mocked result is counted as real inference. Models
and positive-inference images are local setup artifacts; on a fresh machine,
real-model/sample tests explicitly skip until setup is performed. Model-free
checks can be selected with
`python -m pytest -q 06_pose_tracking/tests --ignore=06_pose_tracking/tests/test_pose_real_models.py`.

## Rotation probe and limits

With fresh model instances, public pose.jpg still produced a pose at 0/90/180
image rotations; public right_hands.jpg produced two hand geometries at all three
rotations. A supplied matching homography exposed rack_relative features in all
six runs. This was static sample inference, not a physical rotating-rack trial
or an accuracy benchmark. The pose backend also produced a false-positive body
on the hand-only 90-degree fixture. Published model confidence is not a guarantee
of correctness; evaluate/tune thresholds on the real demo scene.

## Still unverified / external requirements

- [ ] Physical live checklist: known left/right hands, one/both hands, crossing,
      each hand leaving/returning, partial body and moving person
- [ ] Physical rack/setup rotated 90/180 with matching calibration
- [ ] Visual demo-camera handedness and motion-following acceptance
- [ ] Networking physically disabled at OS level (Python sockets are blocked in tests)
- [ ] Real full Modules 01–06 YOLO inference: user's experiment_objects.pt is absent

Manual command:
`python -m 06_pose_tracking --source 0 --show --mirror-display`.
No hands were observed during the recorded 30-frame camera probe; hand inference
is verified on public samples/video instead. Real-scene accuracy and deployment
FPS remain unmeasured. Keep physical demo acceptance open before the final freeze.

The earlier implementation's model-free selection executed successfully: **115 passed, 0 failed** with
`test_pose_real_models.py` excluded. Production weights are not used by this
selection; inference components are explicitly injected fakes except the test
that verifies a missing local model fails initialization.

## Final-review repairs

- [x] Nearby two-hand label swaps reset ambiguous EMA association rather than cross-blending; normal EMA and stale-track behaviour retained
- [x] Module 03 and Module 06 agree on anatomical handedness for mirrored and unmirrored inputs; mirror provenance retained
- [x] VIDEO timestamp reservation survives either inference task failing
- [x] Shared PALM_INDICES reused; source/camera validation precedes model loading
- [x] Display mirroring preserves readable text and leaves inference packets unchanged
- [x] Scoped review staging excludes GUI work and local models; old tracked test artifacts untracked without local deletion

All requested P2 fixes and safe P3 fixes are ready for final independent code
review. Physical demo acceptance above remains open before deployment/freeze;
passing synthetic and sample tests does not establish scene accuracy.

## Commit verification checkpoint

The subsequent pre-commit rerun passed **130 Module 06 tests**, **104 Module 03
tests with 28 skips**, and **948 full-suite tests with 44 skips**, with no failures
or errors. See REPAIR_REVIEW.md for the clean HEAD export procedure. Code freeze
requires the repair and its regression tests in committed HEAD, passing clean
export tests, and no required implementation left only in the working tree or
index. Physical demo acceptance and spacecraft validation are separate from
this code reproducibility decision.
