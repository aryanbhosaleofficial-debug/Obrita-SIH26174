# Procedure Definitions

This folder holds procedure definitions (YAML) loaded by `procedure/procedure_loader.py` and
executed by the Procedure FSM (`procedure/fsm.py`).

Procedures are data, not code: adding or changing an experiment procedure must not require
changing Python files.

## Files

| File | Purpose |
|------|---------|
| `demo_experiment.yaml` | **Example only.** Illustrates the schema with placeholder values. It is not a real ISRO/BAS experiment procedure. |
| `red_yellow_box.yaml` | Four-step inert-box demo, with explicit retry/recovery and event gating. Synthetic semantic events are available through `python -m procedure.demo`. |
| `fusion_touch_move.yaml` | Touch/move labels produced by the existing Module 05 rules; used for end-to-end synthetic pipeline verification. |

## Schema

```yaml
experiment:
  id: "<unique id>"
  name: "<human-readable name>"
  version: "<free text>"

steps:
  - id: "<unique step id>"           # list order = expected order
    description: "<operator guidance text>"
    expected_activity: "<label>"     # must exist in configs/fusion.yaml -> activities.labels
    target_object: "<class name>"    # must exist in configs/classes.yaml
    optional: false
```

## Rules

- Step ids must be unique.
- `expected_activity` values must match the ActivityEvent labels produced by Module 05.
- `target_object` values must match class names in `configs/classes.yaml`.
- The loader must reject a file that breaks these rules instead of guessing.

An optional inline `vocabulary` can declare demo labels instead of using the two
global configs. This does not add recognition capabilities to HAR. Optional
`order`, `alternate_activities`, `timeout_s`, `recovery`, and top-level
`event_policy` are documented in [the FSM README](../procedure/README.md).
Timeouts are metadata only. All examples are prototype procedures, not approved
spacecraft experiment instructions.
