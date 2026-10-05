# Procedure FSM and recovery integration

This is a deterministic prototype procedure-validation layer for the SIH demonstration.
It is not flight-certified procedure-management software.

The FSM owns sequence validation after semantic recognition. It does not inspect
pixels, run HAR, infer experiment safety, or call a speech engine. Procedures and
recovery permissions are data in YAML, not Python experiment logic.

## Repository findings and ownership

Modules 01–05 live in numbered directories, exposed through the `perception`,
`yolo`, `optimization`, `boundary`, and `fusion` packages. Module 06 supplies pose
tracking. `integration.milestone.MilestonePipeline` composes Modules 01–05 and
returns `MilestoneResult.activity`, the existing shared `ActivityEvent`.
Module 05 performs temporal confirmation in `temporal/activity_confirmation.py`
and builds the shared event in `har/activity_event_builder.py`.

`procedure/` was already the shared-event procedure owner. Its existing
`experiment`/`steps` configuration format, loader, `StepOutcome`, and `on_event`
entry point are retained. `procedures/demo_experiment.yaml` remains a placeholder
example validated against `configs/fusion.yaml` and `configs/classes.yaml`.

There is also a separate `yolo.procedure.ProcedureValidator` for the standalone
Module 02 Markdown/fast-action assistant. It has a different event/configuration
contract. That working application is unchanged. Do not route one operator run
through both validators. This integration reuses only its downstream
`AlertEvent`, `AlertManager`, and `EventLog`, without constructing its validator.

The GUI accepts dictionaries through `PipelineBridge.push_snapshot` and
`snapshot_from_dict`. No GUI rewrite is needed.

```text
MilestoneResult.activity / recorded ActivityEvent JSONL
  -> validation + identity/order/duplicate checks
  -> upstream confirmation or lightweight prediction gate
  -> ProcedureFSM: action + object matching, sequence decision
  -> configured recovery policy
  -> GuidanceDecision
  -> ProcedureIntegration
       GUI dictionary -> PipelineBridge.push_snapshot
       AlertEvent     -> AlertManager.enqueue -> existing voice worker
       dictionary     -> EventLog.emit / Python logging
```

## Lifecycle and step states

| ProcedureState | Meaning |
|---|---|
| `NOT_STARTED` | Reset/unstarted; events cannot advance. |
| `READY` | Started, waiting for the first expected action. |
| `IN_PROGRESS` | At least one step complete; awaiting the expected action. |
| `RECOVERY_REQUIRED` | Mismatch; configured retry or operator review required. |
| `PAUSED` | Events ignored until explicit operator resume. |
| `COMPLETED` | All required steps resolved; no next instruction. |
| `ABORTED` | Terminal until reset/start. |
| `ERROR` | Inconsistent internal progress; reset and verify. |

Waiting is represented by READY/IN_PROGRESS; no redundant waiting state.
StepState is independently `PENDING`, `ACTIVE`, `COMPLETED`, `SKIPPED`, or
`RETRY_REQUIRED`. Only explicitly optional steps may become SKIPPED. A detected
missing required step stays unresolved and is reported in `skipped_steps`;
it is never marked completed.

```python
from procedure import ProcedureFSM, ProcedureIntegration, load_procedure

definition = load_procedure("procedures/red_yellow_box.yaml")
fsm = ProcedureFSM(definition=definition)
consumer = ProcedureIntegration(fsm)
consumer.start(source_id="camera-0", session_id="run-001")
decision = consumer.process(activity_event)  # existing shared ActivityEvent
consumer.pause()
consumer.resume()  # explicit operator acknowledgment, not physical correction
consumer.abort()
consumer.reset()
consumer.start(source_id="camera-0", session_id="run-002")
```

`start` without identity binds the first valid input's source/session, including
an unknown observation. `reset` clears progress, stream binding, event ordering,
duplicate memory, prediction confirmation, history, recovery, completion and
alert cooldown. Reset returns to NOT_STARTED and requires start. Controls called
in invalid lifecycle states raise ValueError. Events while paused/terminal are
consumed without advancement, so they cannot be replayed after resume.

`snapshot()` returns a detached frozen `ProcedureSnapshot`: procedure ID, state,
cursor, step statuses, completed IDs, source/session, last valid action/event,
timestamp and recovery action. `history` is a bounded tuple of
`ProcedureHistoryEntry` records containing event ID/time, decision, step before,
step after and message. Snapshot restore and persistent checkpoints are absent.

## Exact input contract

The authoritative class is `shared.schemas.activity_event.ActivityEvent`:

```python
@dataclass
class ActivityEvent:
    event_id: str
    activity_label: str
    frame_id: int
    timestamp_s: float
    start_frame_id: int
    end_frame_id: int
    start_timestamp_s: float
    end_timestamp_s: float
    target_track_id: Optional[int] = None
    target_object_track_id: Optional[int] = None
    target_object_class: Optional[str] = None
    confidence: Optional[float] = None
    evidence_summary: dict[str, float] = field(default_factory=dict)
    conflicts: list[str] = field(default_factory=list)
    status: ModuleStatus = ModuleStatus.OK
    metadata: dict = field(default_factory=dict)
```

Required by default: nonempty `metadata.source_id` and `metadata.session_id`.
Optional `metadata.procedure_id`, if supplied, must match the configured ID.
Module 05 supplies boolean `confirmed` and `emitted` together. Only an explicit
confirmed emission is actionable; the FSM never overrides upstream rejection.
Unknown/current-frame outputs are also safe to pass to `process`.

If both flags are absent, matching action/object/operator track predictions must
pass confidence checks for `confirmation_frames` consecutive frame IDs within
`max_gap_s` per observation. A continuous action emits once. A gap, changed
target/action, invalid input, ignored activity, or low confidence breaks the
sequence; a new occurrence requires fresh confirmation. Input producers must
use unique event IDs for distinct per-frame observations.

Confidence is preserved, including None. Missing confidence is rejected by
default and accepted only with `allow_missing_confidence: true`. This policy
does not fabricate confidence. Status must be OK or DEGRADED, with all other
gates still applied. Input timestamps, intervals, IDs, flags and targets are
validated before state mutation. Invalid/None input returns INVALID_EVENT.

Duplicate IDs are ignored, including IDs already used for pending confirmation.
Both frame ID and timestamp must strictly increase within a run; equal or older
values yield STALE_EVENT. Deduplication is bounded (default 2048 IDs); original
old packets remain stale after eviction. Producers must not rewrite old event
identities/timestamps. Multiple semantic events on one frame are not supported.

A changed source/session/procedure is rejected with SESSION_MISMATCH and cannot
alter the bound procedure. The operator must reset/start to accept a new session.
Malformed input and rejected foreign streams clear pending confirmation.

Legacy `ProcedureFSM(steps=[...])` auto-starts. Legacy `on_event` treats inputs
without confirmation metadata as already confirmed and supplies `legacy` stream
identity. This is compatibility only: new integrations must use `process`.

## Exact output contract

`procedure.contracts.GuidanceDecision` is a frozen dataclass:

```python
@dataclass(frozen=True)
class GuidanceDecision:
    decision: DecisionType
    procedure_id: str
    procedure_state: ProcedureState
    current_step_id: str | None
    current_step_index: int | None
    observed_action: str | None
    expected_action: str | None
    expected_step_id: str | None
    next_step_id: str | None
    next_instruction: str | None
    recovery_action: RecoveryAction | None
    message: str
    severity: GuidanceSeverity
    timestamp_s: float | None
    frame_id: int | None
    event_id: str | None
    source_id: str | None
    session_id: str | None
    confidence: float | None
    completed_steps: tuple[str, ...]
    skipped_steps: tuple[str, ...]
    matching_step_id: str | None
    step_states: tuple[StepProgress, ...]
    should_display: bool
    should_speak: bool
    dedupe_key: str
    metadata: dict[str, Any] = field(default_factory=dict)
```

`StepProgress` holds `step_id: str`, `instruction: str`, `state: StepState`.
Enum values serialize as lowercase strings via `dataclasses.asdict` and JSON.
The current cursor is zero-based and describes state **after** processing;
`expected_action`/`expected_step_id` describe what was expected **before** the
decision. `next_*` points to the pending action, not the step after it. A blocking
recovery, paused/terminal state, or error has no next instruction. The final
correct action returns VALID with state COMPLETED; later inputs return COMPLETED
without speech. Metadata holds detached upstream evidence, bound identity and
the completed step ID when applicable. Nested metadata remains a caller-owned
mutable dictionary; it is not a recursively immutable data structure.

DecisionType values: VALID, WRONG_ORDER, SKIPPED_STEP, REPEATED_ACTION,
UNEXPECTED_ACTION, IGNORED, PENDING_CONFIRMATION, DUPLICATE, STALE_EVENT,
SESSION_MISMATCH, INVALID_EVENT, COMPLETED, STATE_CHANGED, ERROR.
GuidanceSeverity values: INFO, WARNING, ERROR.

## Configuration and recovery

See `../procedures/red_yellow_box.yaml` for the complete four-step configuration.
It preserves the repository's `experiment` and `steps` schema. List order defines
step order; optional `order` must be contiguous starting at 1. Required step
fields are `id`, `description`, `expected_activity`, and `target_object` (explicit
null accepts any object). Optional fields: `optional`, `alternate_activities`,
`timeout_s`, `recovery`. Timeout is metadata only, not an automatic timer.

An inline `vocabulary.activities`/`vocabulary.objects` validates a standalone
demo's labels. Otherwise the loader uses the repository fusion/classes configs
or a supplied config directory. An inline vocabulary does not teach HAR new
actions. The red/yellow labels require an appropriate recognizer or synthetic
events. `fusion_touch_move.yaml` uses the real existing Module 05 rules.

The loader uses `yaml.safe_load`. Missing files raise FileNotFoundError; invalid
schema, fields, identifiers, ordering, recovery actions or ambiguous action/object
matches raise explicit ValueError. Reusing a verb on distinct objects is valid;
overlapping wildcard targets or alternate labels are rejected. Expected labels
cannot also be ignored. Programmatic definitions undergo the same validation.

Step recovery keys are `wrong_order`, `skipped`, `repeated`, `unexpected`:

```yaml
recovery:
  skipped: {action: perform_missing_step}
  repeated: {action: ignore}
  wrong_order:
    action: manual_review
    message: Pause and ask the operator to verify this step.
```

| RecoveryAction | Effect |
|---|---|
| CONTINUE | Keep cursor; accept a later correct event. |
| IGNORE | Keep cursor; no speech for this mismatch. |
| RETRY_CURRENT_STEP | Enter recovery; wait for expected action. |
| PERFORM_MISSING_STEP | Enter recovery; wait for first missing action. |
| PAUSE | Pause; explicit resume acknowledgment required. |
| MANUAL_REVIEW | Block advancement until explicit resume. |
| RESTART_REQUIRED | Block advancement; reset/start required. |

Unconfigured future actions default to MANUAL_REVIEW. Unconfigured repeats and
unrelated actions default to IGNORE; this permits no physical undo or repeat.
Repeat policies belong to the already-completed step; other policies belong to
the currently expected step. The inert-box demo explicitly permits procedural
retry. Correct recovery clears the recovery state and proceeds normally.

Deterministic classification: a future action before any progress is WRONG_ORDER;
a future action after progress is SKIPPED_STEP. Both include matching future step
and every missing intermediate ID, and neither advances required steps. This
is an observation gap, not proof the astronaut physically omitted those actions.

| Observation | Decision / guidance |
|---|---|
| 1 | VALID; next is Step 2. |
| 3 before 1 | WRONG_ORDER; expected Step 1; missing 1 and 2. |
| 1, 3 | SKIPPED_STEP; expected Step 2; no advancement past it. |
| 1, 1 | REPEATED_ACTION; demo ignores without speech. |
| scratch_head | UNEXPECTED_ACTION; cursor unchanged. |
| unknown / idle | IGNORED by default. |
| 1, 3, 2, 3, 4 | Recovery at 2, then normal completion. |
| 1, 2, 3, 4 | VALID each time; final message “Procedure complete.” |

No default message instructs reversing a physical operation. Any physical
correction must come from an explicitly reviewed procedure message.

## GUI, voice and logging integration

```python
from procedure.integration import voice_definition
from yolo.alerts.manager import AlertManager
from yolo.alerts.contracts import VoiceConfig
from yolo.procedure.event_log import EventLog

voice = AlertManager(voice_definition(definition), VoiceConfig())
log = EventLog("outputs/events/procedure.jsonl")
consumer = ProcedureIntegration(
    fsm,
    gui_sink=bridge.push_snapshot,  # existing GUI PipelineBridge
    alert_sink=voice.enqueue,
    log_sink=log.emit,
    reset_alerts=voice.reset,
)
try:
    consumer.start()
    # Inside the existing host pipeline loop:
    # consumer.process(pipeline.process(frame).activity)
finally:
    voice.close()
    log.close()
```

The host serializes calls and owns resource/thread lifecycle. Sinks are optional.
The FSM and dispatcher have no worker threads. Existing GUI/voice queues own
asynchronous delivery. Sink exceptions are logged and reported through
`last_dispatch_errors`; a delivery failure cannot replay a state transition.
An enqueue request is not proof of audible speech; the GUI's `spoken` field is
left empty until a host supplies actual playback status.

Speech uses a key including procedure, stream, state revision, expected step,
decision and recovery. Identical warnings are suppressed within configured event
time cooldown (default five seconds); transitions allow fresh guidance. The
existing AlertManager adds its own host-clock queue/cooldown. Reset its cooldown
through `reset_alerts` when resetting a run. Lifecycle events have no frame/time
in GuidanceDecision; the legacy AlertEvent uses diagnostic zero placeholders.
Alert dispatch uses host monotonic time for playback latency, never video time.

Python logging reports significant transitions and spoken warning requests,
not every frame. The optional EventLog sink records those same significant
decisions. Bounded in-memory history also records suppressed/rejected inputs.
The headless CLI can export displayable decisions via `--guidance`; per-frame
diagnostics include all procedure decisions when `--procedure` is enabled.

## Offline commands and tests

```bash
python -m procedure.demo --procedure red_yellow_box --scenario correct
python -m procedure.demo --procedure red_yellow_box --scenario wrong-order
python -m procedure.demo --procedure red_yellow_box --scenario skip
python -m procedure.demo --procedure red_yellow_box --scenario repeated
python -m procedure.demo --procedure red_yellow_box --scenario recovery
python -m procedure.demo --procedure red_yellow_box --scenario all --json

# Real Modules 01–05 logic with synthetic pixels and fake inference backends:
python scripts/run_fusion.py --synthetic --procedure procedures/fusion_touch_move.yaml --output outputs/events/fusion-frames.jsonl --events outputs/events/fusion-events.jsonl --guidance outputs/events/fusion-guidance.jsonl

# Replay the same shared contract; no inference dependencies needed:
python -m procedure.demo --procedure procedures/fusion_touch_move.yaml --events outputs/events/fusion-events.jsonl

# Existing compatibility entry point:
python main.py

python -m pytest -q tests/procedure
python -m pytest -q
```

`--procedure` is optional for `scripts/run_fusion.py`; absent it, existing
perception behavior/output is preserved. Use its existing camera/video arguments
with local models for live recognition. `--guidance` requires a procedure and
cannot overwrite an input config or share another output path. The headless CLI
does not launch GUI/audio; application hosts attach those sinks explicitly.

## Prototype limitations

Linear, single-operator, single-source sessions only. No branching, persistent
restore, automatic timeout enforcement, rollback, or flight-grade fault handling.
Repeated action/object pairs within a procedure are rejected as ambiguous rather
than guessed. Optional steps may be bypassed only by observing a later matching
step; there is no automatic end-of-procedure skip. Frame and timestamp ordering
are strict. Recognition misses can look like skipped physical actions; operator
verification is necessary for unknown consequences.

The inert-box recovery policy is a demonstration assumption. Real experiments
need reviewed action vocabularies, calibrated recognition, validated recovery
instructions, human authorization, safety engineering and mission certification.
Hardware audio and camera/model availability are separate from deterministic FSM
verification. No real BAS procedure or spacecraft safety rule is supplied here.
