from __future__ import annotations
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QPainter
from PySide6.QtWidgets import (QWidget, QHBoxLayout, QVBoxLayout, QPushButton, QFrame, QSizePolicy)
from .. import theme as T
from .common import label, Rule
from ..state import fmt_met


class Chip(QWidget):
    """Status word with a leading marker square (filled = on, hollow = off)."""
    def __init__(self, text: str):
        super().__init__()
        self.on = True
        self.text = text
        self.setFont(T.font("sans", 13, "semibold"))
        self.set(text, True)

    def set(self, text: str, on: bool):
        self.text, self.on = text, on
        self.setFixedSize(self.fontMetrics().horizontalAdvance(text) + 26, 24)
        self.update()

    def paintEvent(self, _):
        p = QPainter(self)
        p.setPen(Qt.NoPen)
        p.setBrush(T.qc(T.INK) if self.on else T.qc(T.SHEET))
        p.drawRect(0, 8, 9, 9)
        if not self.on:
            p.setPen(T.qc(T.MUTED)); p.setBrush(Qt.NoBrush); p.drawRect(0, 8, 8, 8)
        p.setPen(T.qc(T.INK if self.on else T.MUTED))
        p.setFont(self.font())
        p.drawText(18, 0, self.width() - 18, 24, int(Qt.AlignVCenter | Qt.AlignLeft), self.text)


class Header(QWidget):
    voice_toggled = Signal(bool)

    def __init__(self):
        super().__init__()
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)
        row = QHBoxLayout()
        row.setContentsMargins(24, 14, 24, 14)
        row.setSpacing(18)
        title = QVBoxLayout()
        title.setSpacing(0)
        title.addWidget(label("ORBITA", "sans", 22, "bold", spacing=2.0))
        title.addWidget(label("BAS experiment monitor  ·  SIH26174", "sans", 12, "regular", T.MUTED))
        row.addLayout(title)
        row.addStretch(1)
        self.local = Chip("Local only")
        self.rec = Chip("Recording")
        self.lan = Chip("LAN stream off")
        for c in (self.local, self.rec, self.lan):
            row.addWidget(c)
        self.voice = QPushButton("Voice on")
        self.voice.setCheckable(True)
        self.voice.setChecked(True)
        self.voice.setProperty("seg", True)
        self.voice.setFont(T.font("sans", 13, "semibold"))
        self.voice.setFocusPolicy(Qt.NoFocus)
        self.voice.setCursor(Qt.PointingHandCursor)
        self.voice.toggled.connect(self._voice)
        row.addWidget(self.voice)
        self.demo = label("Demo build, not flight software", "sans", 12, "semibold", T.MUTED)
        row.addWidget(self.demo)
        met = QVBoxLayout()
        met.setSpacing(0)
        met.addWidget(label("MET", "sans", 10, "bold", T.MUTED, align=Qt.AlignRight, spacing=1.2))
        self.met = label("00:00:00", "mono", 22, "semibold", align=Qt.AlignRight)
        self.met.setMinimumWidth(110)
        met.addWidget(self.met)
        row.addLayout(met)
        outer.addLayout(row)
        outer.addWidget(Rule(2))
        self.setAutoFillBackground(True)
        pal = self.palette(); pal.setColor(self.backgroundRole(), T.qc(T.SHEET)); self.setPalette(pal)

    def _voice(self, on: bool):
        self.voice.setText("Voice on" if on else "Voice muted")
        self.voice_toggled.emit(on)

    def apply(self, local_only: bool, recording: bool, lan: bool, voice_on: bool, met: float):
        self.local.set("Local only" if local_only else "Network enabled", local_only)
        self.rec.set("Recording" if recording else "Not recording", recording)
        self.lan.set("LAN stream on" if lan else "LAN stream off", lan)
        if self.voice.isChecked() != voice_on:
            self.voice.blockSignals(True)
            self.voice.setChecked(voice_on)
            self.voice.setText("Voice on" if voice_on else "Voice muted")
            self.voice.blockSignals(False)
        self.met.setText(fmt_met(met))


class StatusBar(QFrame):
    COLORS = {"nominal": (T.NOMINAL, T.INK), "caution": (T.CAUTION, T.INK),
              "warning": (T.WARNING, "#FFFFFF")}
    TAG = {"nominal": "NOMINAL", "caution": "CAUTION", "warning": "WARNING"}

    def __init__(self):
        super().__init__()
        v = QVBoxLayout(self)
        v.setContentsMargins(24, 10, 24, 10)
        v.setSpacing(2)
        row = QHBoxLayout()
        row.setSpacing(14)
        self.tag = label("NOMINAL", "sans", 12, "bold", spacing=1.4)
        self.tag.setFixedWidth(84)
        self.msg = label("", "sans", 18, "semibold")
        self.msg.setWordWrap(True)
        self.msg.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
        self.msg.setMinimumHeight(26)
        row.addWidget(self.tag)
        row.addWidget(self.msg, 1)
        v.addLayout(row)
        self.voice = label("", "mono", 12)
        self.voice.setWordWrap(True)
        self.voice.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
        self.voice.setContentsMargins(98, 0, 0, 0)
        v.addWidget(self.voice)

    def apply(self, level: str, text: str, spoken: str):
        bg, fg = self.COLORS.get(level, self.COLORS["nominal"])
        self.setStyleSheet(f"StatusBar {{ background: {bg}; border: none; }}")
        for l, px, w in ((self.tag, 12, "bold"), (self.msg, 18, "semibold"), (self.voice, 12, "regular")):
            l.setStyleSheet(f"color: {fg}; background: transparent;")
        self.tag.setText(self.TAG.get(level, level.upper()))
        self.msg.setText(text)
        self.voice.setText(f'Voice: "{spoken}"' if spoken else "Voice: none")
