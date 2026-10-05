"""ConsoleWidget: the whole ORBITA screen as one embeddable QWidget."""
from __future__ import annotations
from pathlib import Path
from PySide6.QtCore import Qt, Signal, Slot
from PySide6.QtGui import QImage
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QScrollArea, QSizePolicy)
from . import theme as T
from .state import Snapshot
from .widgets.common import Panel, Segmented, label
from .widgets.table import Table, Column, Cell
from .widgets.camera import CameraView
from .widgets.procedure import ProcedureList
from .widgets.nextstep import NextStepBlock
from .widgets.header import Header, StatusBar

LEVEL_MARK = {"info": T.MUTED, "event": T.INK, "step": T.ACCENT, "voice": T.MUTED,
              "caution": T.CAUTION, "warning": T.WARNING,
              "advisory": T.MUTED}
LEVEL_TEXT = {"caution": T.CAUTION_TEXT, "warning": T.WARNING}


class ConsoleWidget(QWidget):
    """Feed it Snapshots with update_snapshot() and frames with set_frame().

    Signals go outward only: the console never calls into the pipeline.
    """
    voice_toggled = Signal(bool)
    trial_requested = Signal(str)      # demo control only
    rotation_requested = Signal(int)   # demo control only

    TRIALS = [("Correct run", "correct"), ("Skipped step", "skipped"), ("Wrong order", "wrong")]
    ROTATIONS = [("0°", 0), ("90°", 90), ("180°", 180), ("270°", 270)]

    def __init__(self, show_demo_controls: bool = True, parent: QWidget | None = None):
        super().__init__(parent)
        self.setAutoFillBackground(True)
        self.setObjectName("console")
        self.setStyleSheet(f"QWidget#console {{ background: {T.PAPER}; }}")
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        self.header = Header()
        self.header.voice_toggled.connect(self.voice_toggled)
        self.status = StatusBar()
        root.addWidget(self.header)
        root.addWidget(self.status)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        body = QWidget()
        body.setObjectName("body")
        body.setStyleSheet(f"QWidget#body {{ background: {T.PAPER}; }}")
        bv = QVBoxLayout(body)
        bv.setContentsMargins(24, 20, 24, 16)
        bv.setSpacing(18)
        cols = QHBoxLayout()
        cols.setSpacing(28)
        cols.setAlignment(Qt.AlignTop)
        left, right = QVBoxLayout(), QVBoxLayout()
        for c in (left, right):
            c.setSpacing(20)
            c.setAlignment(Qt.AlignTop)
        cols.addLayout(left, 10)
        cols.addLayout(right, 11)
        bv.addLayout(cols)

        # ---- left column
        self.camera = CameraView()
        cam_box = QWidget()
        cb = QVBoxLayout(cam_box)
        cb.setContentsMargins(0, 0, 0, 0)
        cb.setSpacing(10)
        cb.addWidget(self.camera)
        self.demo_row = QWidget()
        dr = QHBoxLayout(self.demo_row)
        dr.setContentsMargins(0, 0, 0, 0)
        dr.setSpacing(24)
        self.trial_seg = Segmented("Trial", self.TRIALS)
        self.rot_seg = Segmented("Rotation", self.ROTATIONS)
        self.trial_seg.chosen.connect(lambda k: self.trial_requested.emit(str(k)))
        self.rot_seg.chosen.connect(lambda d: self.rotation_requested.emit(int(d)))
        dr.addWidget(self.trial_seg)
        dr.addWidget(self.rot_seg)
        dr.addStretch(1)
        cb.addWidget(self.demo_row)
        self.demo_row.setVisible(show_demo_controls)
        self.cam_panel = Panel("Camera 0", cam_box, "Boundary and rack axes are drawn from detections")
        left.addWidget(self.cam_panel)

        self.readings = Table([Column("Object", flex=1.4, bold=True), Column("X", 80, align="right", mono=True),
                               Column("Y", 80, align="right", mono=True),
                               Column("Aspect", 80, align="right", mono=True),
                               Column("Conf.", 70, align="right", mono=True)], row_h=30)
        left.addWidget(Panel("Position in the rack frame", self.readings, "unaffected by setup rotation"))

        self.chain = Table([Column("Stage", 96, bold=True), Column("Module", flex=1.0, mono=True),
                            Column("Note", flex=1.6), Column("Status", 104, align="right", bold=True)],
                           row_h=30)
        left.addWidget(Panel("Processing chain", self.chain))

        # ---- right column
        self.next = NextStepBlock()
        right.addWidget(self.next)
        self.proc = ProcedureList()
        self.proc_panel = Panel("Procedure", self.proc)
        right.addWidget(self.proc_panel)
        self.alerts = Table([Column("Time", 76, mono=True), Column("Level", 92, bold=True),
                             Column("Message", flex=1.0)], row_h=30)
        right.addWidget(Panel("Alerts", self.alerts))
        self.log = Table([Column("Time", 100, mono=True), Column("Level", 80, bold=True),
                          Column("Event", 116, mono=True), Column("Detail", flex=1.0),
                          Column("Conf.", 52, align="right", mono=True)], row_h=28, px=12)
        self.log_panel = Panel("Event log", self.log, "")
        right.addWidget(self.log_panel)

        # ---- footer (always last, in the scroll area, never over anything)
        self.footer = label("", "sans", 12, "regular", T.MUTED, wrap=True)
        self.footer.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
        bv.addWidget(self.footer)
        bv.addStretch(1)
        scroll.setWidget(body)
        root.addWidget(scroll, 1)
        self.snapshot = Snapshot(voice_on=False)
        self.update_snapshot(self.snapshot)

    # ---------------------------------------------------------------- public API
    @Slot(QImage)
    def set_frame(self, img: QImage | None):
        self.camera.set_frame(img)

    def set_demo_state(self, trial: str | None, rotation: int):
        if trial:
            self.trial_seg.set_value(trial)
        self.rot_seg.set_value(rotation)

    @Slot(object)
    def update_snapshot(self, s: Snapshot):
        self.snapshot = s
        self.header.apply(s.local_only, s.recording, s.lan_streaming, s.voice_on, s.met_seconds)
        for chip, name, enabled in ((self.header.rec, "Recording", s.recording),
                                    (self.header.lan, "Streaming", s.lan_streaming)):
            status = s.system_health.get(name)
            if status and status != "OK":
                chip.set(f"{name}: {status}", enabled)
        self.header.voice.setToolTip(f"Voice: {s.system_health.get('Voice', 'OFF')}")
        self.status.apply(s.status_level, s.status_text, s.spoken)
        self.camera.set_scene(s.scene, s.stamp)
        if s.source_id:
            self.camera.cam_label = s.source_id
            self.cam_panel.title.setText("SOURCE")
            self.cam_panel.title.setToolTip(s.source_id)
        self.next.apply(s.next_step)
        self.proc.set_steps(s.steps)
        self.proc_panel.set_right(f"{s.procedure_state.replace('_', ' ')} · {sum(1 for x in s.steps if x.state == 'done')} of {len(s.steps)} complete")
        self.readings.set_rows([[r.name, _f(r.x), _f(r.y), _f(r.aspect), _f(r.conf)] for r in s.readings])
        self.chain.set_rows([[c.stage, c.module, c.note, c.status] for c in s.chain])
        self.alerts.set_rows([[a.t, Cell(a.level.capitalize(), LEVEL_TEXT.get(a.level), marker=LEVEL_MARK.get(a.level)),
                               a.text] for a in reversed(s.alerts)])
        self.log.set_rows([[e.t, Cell(e.level, LEVEL_TEXT.get(e.level), marker=LEVEL_MARK.get(e.level)),
                            e.event, e.detail, _f(e.conf)] for e in reversed(s.log)])
        self.log_panel.set_right(Path(s.log_path).name if s.log_path else "")
        self.log_panel.right.setToolTip(s.log_path)
        self.footer.setText(s.footer)


def _f(v) -> str:
    return "—" if v is None else f"{v:.2f}"
