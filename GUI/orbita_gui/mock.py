"""Built-in SAMPLE data for the standalone demo. Nothing here is measured output.

Step names, timings, confidences and log lines are placeholders that mirror the design
reference; the real procedure file and pipeline replace them when embedded.
"""
from __future__ import annotations
import copy, time
from PySide6.QtCore import QObject, QTimer, Signal
from .state import (Snapshot, Step, Detection, Hand, Reading, ChainItem, LogEntry, AlertEntry,
                    NextStep, Scene)

PROC = [("pick_red", "Pick up the red box"), ("place_red", "Place the red box on the rack spot"),
        ("pick_yellow", "Pick up the yellow box"), ("rotate_yellow", "Rotate the yellow box by 90°"),
        ("place_yellow", "Place the yellow box on the rack spot")]
FOOTER = ("Rack-relative values are measured against main_box on a ground demo setup. "
          "Sample data, not pipeline output. Accuracy, FPS and per-module timing are not measured.")
LOG_PATH = "logs/20261005_0942_events.jsonl"

_BASE_LOG = [
    ("00:00:12.040", "info", "session_start", "procedure=procedures/red_yellow_box.md steps=5", None),
    ("00:00:12.311", "info", "camera", "source=0 opened once, timestamps increasing", None),
    ("00:00:38.902", "event", "pick", "object=red_box confirmed over 300 ms", 0.93),
    ("00:00:41.120", "step", "pick_red", "state=done", None),
    ("00:00:41.140", "voice", "speak", '"Step 1 complete. Next: place the red box."', None),
]
_MID_LOG = [
    ("00:01:19.455", "event", "place", "object=red_box back at rest and still", 0.90),
    ("00:01:21.870", "step", "place_red", "state=done", None),
    ("00:01:22.004", "voice", "speak", '"Step 2 complete. Next: pick up the yellow box."', None),
]
_ADV = [AlertEntry("00:00:41", "advisory", "Step 1 complete. Next: place the red box.")]
_ADV2 = _ADV + [AlertEntry("00:01:22", "advisory", "Step 2 complete. Next: pick up the yellow box.")]

TRIALS = {
    "correct": dict(
        states=["done", "done", "active", "pending", "pending"], times=["00:00:41", "00:01:22", "", "", ""],
        met=98, stamp=98.207, conf=0.88, yconf=0.88, level="nominal",
        text="Procedure on track. Step 2 confirmed.", spoken="Step 2 complete. Next: pick up the yellow box.",
        nxt=NextStep("03", "Next step", "Pick up the yellow box",
                     "A pick is confirmed after 300 ms of consistent detection.", 0.71, "PICK yellow_box · 212 / 300 ms"),
        log=_BASE_LOG + _MID_LOG + [("00:01:38.207", "event", "pick", "object=yellow_box candidate 212 / 300 ms", 0.88)],
        alerts=_ADV2),
    "skipped": dict(
        states=["done", "done", "skipped", "active", "pending"], times=["00:00:41", "00:01:22", "", "", ""],
        met=105, stamp=105.020, conf=0.84, yconf=0.84, level="caution",
        text="Step 3 (pick_yellow) was skipped. Step 4 is in progress.",
        spoken="Step 3 skipped. Pick up the yellow box first.",
        nxt=NextStep("03", "Return to", "Pick up the yellow box", "Then continue with step 04, rotate_yellow.",
                     1.0, "ROTATE yellow_box · 300 / 300 ms"),
        log=_BASE_LOG + _MID_LOG + [
            ("00:01:44.610", "event", "manipulate", "object=yellow_box rotating, confirmed over 300 ms", 0.84),
            ("00:01:44.912", "step", "rotate_yellow", "state=active, pick_yellow=skipped", None),
            ("00:01:44.930", "caution", "skipped", "steps=[pick_yellow]", None),
            ("00:01:45.020", "voice", "speak", '"Step 3 skipped. Pick up the yellow box first."', None)],
        alerts=_ADV2 + [AlertEntry("00:01:45", "caution", "Step 3 skipped. Pick up the yellow box first.")]),
    "wrong": dict(
        states=["done", "active", "wrong", "pending", "pending"], times=["00:00:41", "", "", "", ""],
        met=64, stamp=63.700, conf=0.89, yconf=0.89, level="warning",
        text="Pick yellow detected while step 2 (place_red) is expected.",
        spoken="Wrong order. Place the red box first.",
        nxt=NextStep("02", "Do first", "Place the red box on the rack spot", "Then continue with step 03, pick_yellow.",
                     1.0, "PICK yellow_box · 300 / 300 ms · not expected"),
        log=_BASE_LOG + [
            ("00:01:03.340", "event", "pick", "object=yellow_box confirmed over 300 ms", 0.89),
            ("00:01:03.642", "warning", "wrong_order", "expected=place_red got=pick_yellow", None),
            ("00:01:03.700", "voice", "speak", '"Wrong order. Place the red box first."', None)],
        alerts=_ADV + [AlertEntry("00:01:03", "warning", "Wrong order. Place the red box first.")]),
}


def _stamp(sec: float) -> str:
    ms = int(round(sec * 1000))
    return f"{ms // 3600000:02d}:{(ms // 60000) % 60:02d}:{(ms // 1000) % 60:02d}.{ms % 1000:03d}"


def build_snapshot(key: str, rotation: int, elapsed: float = 0.0, voice_on: bool = True) -> Snapshot:
    t = TRIALS[key]
    scene = Scene(
        simulated=True, rotation=rotation,
        main_box=Detection("main_box", 0.97, 0.50, 0.50, 0.24, 0.30, dashed=True),
        objects=[Detection("red_box", 0.93, 0.32, 0.338, 0.10, 0.14, color="#A94437"),
                 Detection("yellow_box", t["yconf"], 0.673, 0.645, 0.10, 0.14, color="#C9A431", label_below=True)],
        hands=[Hand(tip=(0.632, 0.585), wrist=(0.59, 0.64), conf=0.81)])
    return Snapshot(
        status_level=t["level"], status_text=t["text"], spoken=t["spoken"],
        met_seconds=t["met"] + elapsed, stamp=_stamp(t["stamp"] + elapsed), confidence=t["conf"],
        steps=[Step(pid, txt, st, tm) for (pid, txt), st, tm in zip(PROC, t["states"], t["times"])],
        next_step=copy.copy(t["nxt"]),
        readings=[Reading("red_box", -0.75, -0.38, 1.27, 0.93), Reading("yellow_box", 0.72, 0.34, 1.27, t["yconf"]),
                  Reading("hand index tip", 0.55, 0.20, None, 0.81)],
        chain=[ChainItem("Camera", "OpenCV", "Opened once"), ChainItem("YOLO", "best.pt", "Required"),
               ChainItem("Hands", "MediaPipe", "Adapter"), ChainItem("Shape", "Boundary", "Adapter"),
               ChainItem("Events", "Interaction", "Pick, manipulate, place"),
               ChainItem("Steps", "Checker", "Reads the .md procedure")],
        alerts=list(t["alerts"]), log=[LogEntry(*e) for e in t["log"]], log_path=LOG_PATH,
        scene=scene, recording=True, lan_streaming=False, local_only=True, voice_on=voice_on, footer=FOOTER)


class MockProvider(QObject):
    """Emits sample Snapshots. Stands in for the pipeline in the standalone demo."""
    snapshot = Signal(object)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.trial, self.rotation, self.voice_on = "correct", 0, True
        self._t0 = time.monotonic()
        self._timer = QTimer(self)
        self._timer.setInterval(200)
        self._timer.timeout.connect(self.emit_now)

    def start(self):
        self._t0 = time.monotonic()
        self._timer.start()
        self.emit_now()

    def stop(self):
        self._timer.stop()

    def set_trial(self, key: str):
        self.trial, self._t0 = key, time.monotonic()
        self.emit_now()

    def set_rotation(self, deg: int):
        self.rotation = deg
        self.emit_now()

    def set_voice(self, on: bool):
        self.voice_on = on
        self.emit_now()

    def emit_now(self):
        self.snapshot.emit(build_snapshot(self.trial, self.rotation, time.monotonic() - self._t0, self.voice_on))
