"""Plain data the GUI draws. No Qt imports, so a pipeline thread can build these freely.

The GUI never reads pipeline objects directly. Anything that wants to be shown is
copied into a Snapshot (see adapters.py for dict / duck-typed conversion).
"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Optional

STEP_STATES = ("done", "active", "pending", "skipped", "wrong")
LEVELS = ("nominal", "caution", "warning")      # status bar levels


@dataclass
class Step:
    id: str                 # e.g. "pick_red" (id from the procedure file)
    text: str               # operator-facing sentence
    state: str = "pending"  # one of STEP_STATES
    time: str = ""          # "00:00:41" when finished, else ""


@dataclass
class Detection:
    """A detected object in normalised frame coordinates (0..1, centre + size)."""
    name: str
    conf: Optional[float]
    cx: float
    cy: float
    w: float
    h: float
    color: Optional[str] = None     # fill colour for the simulated scene only
    label_below: bool = False
    dashed: bool = False            # dashed outline for reference regions (main_box)


@dataclass
class Hand:
    tip: tuple[float, float]
    wrist: tuple[float, float]
    conf: float = 0.0


@dataclass
class Reading:
    """Rack-relative reading. None shows as an em dash."""
    name: str
    x: Optional[float] = None
    y: Optional[float] = None
    aspect: Optional[float] = None
    conf: Optional[float] = None


@dataclass
class ChainItem:
    stage: str
    module: str
    note: str
    status: str = "OK"


@dataclass
class LogEntry:
    t: str
    level: str          # info | event | step | voice | caution | warning
    event: str
    detail: str = ""
    conf: Optional[float] = None


@dataclass
class AlertEntry:
    t: str
    level: str          # advisory | caution | warning
    text: str


@dataclass
class NextStep:
    number: str = ""
    head: str = "Next step"
    text: str = ""
    note: str = ""
    progress: float = 0.0            # 0..1
    progress_label: str = ""


@dataclass
class Scene:
    """Overlay geometry. `simulated=True` makes the camera widget paint the demo rack scene."""
    simulated: bool = True
    overlays_rendered: bool = False  # integration frame already contains source-coordinate overlays
    rotation: int = 0                # setup rotation in degrees (demo scene only)
    main_box: Optional[Detection] = None
    objects: list[Detection] = field(default_factory=list)
    hands: list[Hand] = field(default_factory=list)
    rack_origin: tuple[float, float] = (0.36, 0.32)
    rack_len: float = 0.12           # fraction of frame width


@dataclass
class Snapshot:
    status_level: str = "nominal"
    status_text: str = "Waiting for pipeline."
    spoken: str = ""
    met_seconds: float = 0.0         # mission elapsed time shown in the header
    stamp: str = "00:00:00.000"      # camera HUD timestamp
    confidence: Optional[float] = None
    steps: list[Step] = field(default_factory=list)
    next_step: NextStep = field(default_factory=NextStep)
    readings: list[Reading] = field(default_factory=list)
    chain: list[ChainItem] = field(default_factory=list)
    alerts: list[AlertEntry] = field(default_factory=list)
    log: list[LogEntry] = field(default_factory=list)       # oldest first; GUI shows newest first
    log_path: str = ""
    scene: Scene = field(default_factory=Scene)
    recording: bool = False
    lan_streaming: bool = False
    local_only: bool = True
    voice_on: bool = True
    footer: str = ""


def fmt_met(seconds: float) -> str:
    s = max(0, int(seconds))
    return f"{s // 3600:02d}:{(s % 3600) // 60:02d}:{s % 60:02d}"
