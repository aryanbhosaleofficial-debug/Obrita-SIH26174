from __future__ import annotations
from PySide6.QtCore import Qt, QRectF, QPointF
from PySide6.QtGui import QPainter, QPen
from PySide6.QtWidgets import QWidget, QSizePolicy
from .. import theme as T
from ..state import Step

ROW_H = 62
STATE_LABEL = {"done": "Done", "active": "In progress", "pending": "Pending",
               "skipped": "Skipped", "wrong": "Wrong order"}
STATE_BAR = {"active": T.ACCENT, "skipped": T.CAUTION, "wrong": T.WARNING}


class ProcedureList(QWidget):
    def __init__(self):
        super().__init__()
        self.steps: list[Step] = []
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self._fit()

    def set_steps(self, steps: list[Step]):
        self.steps = steps
        self._fit()
        self.update()

    def _fit(self):
        self.setFixedHeight(max(1, len(self.steps)) * ROW_H + 1)

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHints(QPainter.Antialiasing | QPainter.TextAntialiasing)
        p.fillRect(self.rect(), T.qc(T.SHEET))
        for i, s in enumerate(self.steps):
            y = i * ROW_H
            row = QRectF(0, y, self.width(), ROW_H)
            if s.state == "active":
                p.fillRect(row, T.qc("#E3E8EF"))
            if s.state in STATE_BAR:
                p.fillRect(QRectF(0, y, 5, ROW_H), T.qc(STATE_BAR[s.state]))
            self._glyph(p, QRectF(20, y + ROW_H / 2 - 10, 20, 20), s.state)
            p.setFont(T.font("mono", 13, "semibold"))
            p.setPen(T.qc(T.MUTED))
            p.drawText(QRectF(52, y, 30, ROW_H), int(Qt.AlignVCenter | Qt.AlignLeft), f"{i + 1:02d}")
            right_w = 104
            tx = 86
            tw = self.width() - tx - right_w - 12
            fam = T.font("sans", 15, "semibold" if s.state != "pending" else "regular")
            p.setFont(fam)
            p.setPen(T.qc(T.MUTED if s.state == "pending" else T.INK))
            txt = p.fontMetrics().elidedText(s.text, Qt.ElideRight, int(tw))
            p.drawText(QRectF(tx, y + 9, tw, 24), int(Qt.AlignVCenter | Qt.AlignLeft), txt)
            p.setFont(T.font("mono", 11))
            p.setPen(T.qc(T.MUTED))
            p.drawText(QRectF(tx, y + 33, tw, 18), int(Qt.AlignVCenter | Qt.AlignLeft), s.id)
            # right: state label + time
            col = {"skipped": T.CAUTION_TEXT, "wrong": T.WARNING, "active": T.ACCENT}.get(s.state, T.INK)
            p.setFont(T.font("sans", 12, "bold", 0.5))
            p.setPen(T.qc(col if s.state != "pending" else T.MUTED))
            p.drawText(QRectF(self.width() - right_w - 12, y + 9, right_w, 22),
                       int(Qt.AlignVCenter | Qt.AlignRight), STATE_LABEL.get(s.state, s.state).upper())
            if s.time:
                p.setFont(T.font("mono", 11))
                p.setPen(T.qc(T.MUTED))
                p.drawText(QRectF(self.width() - right_w - 12, y + 33, right_w, 18),
                           int(Qt.AlignVCenter | Qt.AlignRight), s.time)
            p.setPen(T.qc(T.HAIR))
            p.drawLine(0, int(y + ROW_H) - 1, self.width(), int(y + ROW_H) - 1)

    @staticmethod
    def _glyph(p: QPainter, b: QRectF, state: str):
        p.save()
        ink, acc = T.qc(T.INK), T.qc(T.ACCENT)
        if state == "done":
            p.setPen(Qt.NoPen); p.setBrush(ink); p.drawRect(b)
            p.setPen(QPen(T.qc(T.SHEET), 2.4)); 
            p.drawLine(QPointF(b.left() + 4.5, b.center().y() + 0.5), QPointF(b.left() + 8.5, b.bottom() - 5.5))
            p.drawLine(QPointF(b.left() + 8.5, b.bottom() - 5.5), QPointF(b.right() - 4, b.top() + 5))
        elif state == "active":
            p.setPen(QPen(acc, 2.4)); p.setBrush(Qt.NoBrush); p.drawRect(b.adjusted(1, 1, -1, -1))
            p.setPen(Qt.NoPen); p.setBrush(acc); p.drawRect(b.adjusted(6, 6, -6, -6))
        elif state == "skipped":
            p.setPen(QPen(T.qc(T.CAUTION), 2.4)); p.setBrush(Qt.NoBrush); p.drawRect(b.adjusted(1, 1, -1, -1))
            p.setPen(QPen(T.qc(T.CAUTION_TEXT), 2.4))
            p.drawLine(QPointF(b.left() + 5, b.center().y()), QPointF(b.right() - 5, b.center().y()))
        elif state == "wrong":
            p.setPen(Qt.NoPen); p.setBrush(T.qc(T.WARNING)); p.drawRect(b)
            p.setPen(QPen(T.qc("#FFFFFF"), 2.4))
            p.drawLine(QPointF(b.left() + 5, b.top() + 5), QPointF(b.right() - 5, b.bottom() - 5))
            p.drawLine(QPointF(b.right() - 5, b.top() + 5), QPointF(b.left() + 5, b.bottom() - 5))
        else:
            p.setPen(QPen(T.qc(T.MUTED), 1.8)); p.setBrush(Qt.NoBrush); p.drawRect(b.adjusted(1, 1, -1, -1))
        p.restore()
