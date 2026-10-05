from __future__ import annotations
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QPainter
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame,
                               QPushButton, QButtonGroup, QSizePolicy)
from .. import theme as T


def label(text: str = "", kind="sans", px=14, weight="regular", color=T.INK,
          wrap=False, align=None, spacing=0.0) -> QLabel:
    l = QLabel(text)
    l.setFont(T.font(kind, px, weight, spacing))
    l.setStyleSheet(f"color: {color}; background: transparent;")
    l.setWordWrap(wrap)
    l.setTextInteractionFlags(Qt.NoTextInteraction)
    if align:
        l.setAlignment(align)
    return l


class Rule(QFrame):
    def __init__(self, px: int = 2, color: str = T.INK):
        super().__init__()
        self.setFixedHeight(px)
        self.setStyleSheet(f"background: {color}; border: none;")


class Panel(QWidget):
    """Section with a heavy top rule, an uppercase title and an optional right-hand note."""
    def __init__(self, title: str, body: QWidget | None = None, right: str = ""):
        super().__init__()
        v = QVBoxLayout(self)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(0)
        v.addWidget(Rule(2))
        head = QHBoxLayout()
        head.setContentsMargins(0, 8, 0, 8)
        self.title = label(title.upper(), "sans", 12, "bold", T.INK, spacing=1.2)
        self.right = label(right, "mono", 11, "regular", T.MUTED)
        self.right.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self.right.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)  # never forces width
        head.addWidget(self.title)
        head.addWidget(self.right, 1)
        v.addLayout(head)
        self.body_layout = v
        if body is not None:
            v.addWidget(body)

    def add(self, w: QWidget):
        self.body_layout.addWidget(w)

    def set_right(self, text: str):
        self.right.setText(text)


class Segmented(QWidget):
    """Row of exclusive buttons. Emits the data value of the clicked option."""
    chosen = Signal(object)

    def __init__(self, caption: str, options: list[tuple[str, object]]):
        super().__init__()
        h = QHBoxLayout(self)
        h.setContentsMargins(0, 0, 0, 0)
        h.setSpacing(0)
        h.addWidget(label(caption.upper(), "sans", 11, "bold", T.MUTED, spacing=1.0))
        h.addSpacing(10)
        self.group = QButtonGroup(self)
        self.group.setExclusive(True)
        self.buttons: dict[object, QPushButton] = {}
        for text, data in options:
            b = QPushButton(text)
            b.setCheckable(True)
            b.setProperty("seg", True)
            b.setFont(T.font("sans", 13, "semibold"))
            b.setCursor(Qt.PointingHandCursor)
            b.setFocusPolicy(Qt.NoFocus)
            b.clicked.connect(lambda _=False, d=data: self.chosen.emit(d))
            self.group.addButton(b)
            self.buttons[data] = b
            h.addWidget(b)
        h.addStretch(1)

    def set_value(self, data):
        if data in self.buttons:
            self.buttons[data].setChecked(True)
