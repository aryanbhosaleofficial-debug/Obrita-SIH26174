# Procedure FSM verification

Verified on 2026-10-05 with Python 3.14.7, from the repository root.

The starting working tree already contained substantial uncommitted procedure
implementation and tests. Those changes were preserved and completed in place.
The baseline below describes that starting working tree, not a pristine Git HEAD.

| Command / checkpoint | Passed | Failed | Skipped | Errors |
|---|---:|---:|---:|---:|
| Initial `python -m pytest -q`, sandbox | 0 | 0 | 0 | 1 collection error |
| Baseline `python -m pytest -q`, permitted execution | 1074 | 0 | 44 | 0 |
| Final `python -m pytest -q tests/procedure tests/test_procedure_runtime.py tests/test_full_pipeline.py` | 141 | 0 | 0 | 0 |
| Final `python -m pytest -q tests/procedure` | 132 | 0 | 0 | 0 |
| Final `python -m pytest -q` | 1080 | 0 | 44 | 0 |

Initial collection was blocked by Windows access denial on `.pytest_cache`.
The exact command passed after permitted execution outside the sandbox. No test
configuration changes, deletions, or new skips were used to obtain passing results.
The final full suite took 24.50 seconds; standalone procedure tests took 2.52 seconds.
The baseline and final suites have the same 44 skips. There are no observed new
regressions. Passing synthetic tests does not certify physical experiment behavior.

## Executed demonstrations

`python -m procedure.demo --procedure red_yellow_box --scenario all` exited 0:

- Correct: four VALID actions, COMPLETED, no next step.
- Wrong order: action 3 first, WRONG_ORDER, missing steps 1 and 2, cursor unchanged.
- Skip: actions 1 and 3, SKIPPED_STEP, step 2 unresolved.
- Repeated: actions 1 and 1, REPEATED_ACTION, only step 1 complete.
- Recovery: actions 1, 3, 2, 3, 4, recovered at step 2 and completed all four.

`python main.py` exited 0 and completed the existing two-step placeholder demo.

```bash
python scripts/run_fusion.py --synthetic --procedure procedures/fusion_touch_move.yaml --output outputs/events/procedure-verification-frames.jsonl --events outputs/events/procedure-verification-events.jsonl --guidance outputs/events/procedure-verification-guidance.jsonl
python -m procedure.demo --procedure procedures/fusion_touch_move.yaml --events outputs/events/procedure-verification-events.jsonl
```

Both commands exited 0. The actual Module 05 code emitted two recognized events
from 36 synthetic frames, with zero invalid frames. The FSM accepted touch_object
then move_object and completed. Replaying the shared event JSONL produced the
same progression. Optional pose was disabled. These ignored output artifacts are
local verification data, not source files.

`git diff --check` passed. Git emitted only Windows LF/CRLF normalization notices.

## Coverage and scope

The procedure suite verifies lifecycle, complete sequences, wrong order, missing
steps, repeated and unrelated actions, explicit optional skips, recovery policies,
operator acknowledgment, session/source isolation, malformed inputs, missing
confidence, duplicates, stale events, bounded history, state-corruption handling,
reset, alternates, loader failures, multi-frame gating and voice cooldown.

Integration checks use real Module 05 logic with injected inference fakes, the
actual GUI snapshot adapter, AlertEvent and EventLog contracts, disabled
AlertManager construction, sink failures, JSON replay, and both CLI entry points.
New regression checks cover duplicate IDs during pending confirmation, renewed
confirmation after frame/time gaps, the live CLI procedure connection, output
path protection, and synthetic GUI labeling.

No live camera, audible hardware playback, or real BAS procedure was validated
by this module verification. GUI/voice use existing downstream components;
the host remains responsible for their resource lifecycle and operator controls.

## Freeze recommendation

Freeze the deterministic prototype module: core and integration tests pass, all
demo scenarios behave as specified, and the full suite has no new regressions.
This recommendation does not apply to spacecraft certification or the accuracy
of future red/yellow-box perception models.
