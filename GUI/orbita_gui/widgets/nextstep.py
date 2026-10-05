from __future__ import annotations
from PySide6.QtCore import Qt, QRectF
from PySide6.QtGui import QPainter
from PySide6.QtWidgets import QFrame, QVBoxLayout, QHBoxLayout, QWidget, QSizePolicy
from .. import theme as T
from .common import label
from ..state import NextStep


class _Bar(QWidget):
    def __init__(self):
        super().__init__()
        self.value = 0.0
        self.setFixedHeight(6)

    def paintEvent(self, _):
        p = QPainter(self)
        p.fillRect(self.rect(), T.qc("#CDD2D7"))
        p.fillRect(QRectF(0, 0, self.width() * max(0.0, min(1.0, self.value)), self.height()), T.qc(T.ACCENT))


class NextStepBlock(QFrame):
    def __init__(self):
        super().__init__()
        self.setStyleSheet(f"NextStepBlock {{ background: {T.SHEET}; border: 2px solid {T.INK}; }}")
        v = QVBoxLayout(self)
        v.setContentsMargins(18, 14, 18, 16)
        v.setSpacing(6)
        self.head = label("NEXT STEP", "sans", 12, "bold", T.ACCENT, spacing=1.4)
        v.addWidget(self.head)
        row = QHBoxLayout()
        row.setSpacing(14)
        self.num = label("", "mono", 22, "semibold", T.ACCENT)
        self.num.setMinimumWidth(36)
        self.num.setAlignment(Qt.AlignTop | Qt.AlignLeft)
        self.text = label("", "sans", 22, "semibold", wrap=True)
        self.text.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
        row.addWidget(self.num)
        row.addWidget(self.text, 1)
        v.addLayout(row)
        self.note = label("", "sans", 13, "regular", T.MUTED, wrap=True)
        self.note.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
        v.addWidget(self.note)
        v.addSpacing(4)
        self.confirm = label("", "mono", 12, "regular", T.INK)
        v.addWidget(self.confirm)
        self.bar = _Bar()
        v.addWidget(self.bar)

    def apply(self, n: NextStep):
        self.head.setText(n.head.upper())
        self.num.setText(n.number)
        self.text.setText(n.text)
        self.note.setText(n.note)
        self.confirm.setText(n.progress_label)
        self.bar.value = n.progress
        self.bar.update()
