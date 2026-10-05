from dataclasses import replace
from pathlib import Path
import pytest

from procedure import ProcedureFSM, load_procedure
from shared.schemas.activity_event import ActivityEvent

ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture
def definition():
    return load_procedure(ROOT / "procedures/red_yellow_box.yaml")


@pytest.fixture
def fsm(definition):
    result = ProcedureFSM(definition=definition)
    result.start()
    return result


@pytest.fixture
def event(definition):
    counter = [0]
    def make(step=0, *, frame=None, timestamp=None, raw=False, confidence=.9,
             source="camera", session="run", event_id=None, **changes):
        frame = counter[0] + 1 if frame is None else frame
        counter[0] = max(counter[0], frame)
        timestamp = float(frame) if timestamp is None else timestamp
        selected = definition.steps[step] if isinstance(step, int) else None
        metadata = {"source_id": source, "session_id": session, "test_evidence": {"retained": True}}
        if not raw:
            metadata.update(confirmed=True, emitted=True)
        value = ActivityEvent(event_id or f"event-{frame}", selected.expected_activity if selected else step,
                              frame, timestamp, frame, frame, timestamp, timestamp,
                              target_object_class=selected.target_object if selected else None,
                              confidence=confidence, metadata=metadata)
        return replace(value, **changes)
    return make
