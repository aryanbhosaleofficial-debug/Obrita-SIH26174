from dataclasses import dataclass, field
from typing import List, Optional

@dataclass
class StepState:
    id: str
    name: str
    status: str  # "done", "active", "pending", "skipped", "wrong"
    time: str

@dataclass
class EventLogLine:
    time: str
    level: str  # "info", "event", "step", "voice", "caution", "warning"
    event: str
    detail: str
    conf: str = ""

@dataclass
class Alert:
    time: str
    level: str  # "Advisory", "Caution", "Warning"
    message: str

@dataclass
class NextStep:
    step_num: str
    title: str
    note: str
    progress_text: str
    progress_pct: int
    conf: str = ""

@dataclass
class StatusSnapshot:
    trial_name: str
    met: str
    frame_time: str
    status_level: str  # "Nominal", "Caution", "Warning"
    status_message: str
    spoken_text: str
    steps: List[StepState]
    next_step: NextStep
    alerts: List[Alert]
    events: List[EventLogLine]
    rotation_deg: int = 0
    voice_muted: bool = False
