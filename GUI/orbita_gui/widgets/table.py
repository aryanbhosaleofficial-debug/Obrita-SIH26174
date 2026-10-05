from __future__ import annotations
from dataclasses import dataclass
from typing import Union
from PySide6.QtCore import Qt, QRectF, QSize
from PySide6.QtGui import QPainter, QColor
from PySide6.QtWidgets import QWidget, QSizePolicy
from .. import theme as T


@dataclass
class Column:
    title: str
    w: int = 0              # fixed px; 0 = flexible
    flex: float = 1.0
    align: str = "left"     # left | right
    mono: bool = False
    bold: bool = False


@dataclass
class Cell:
    text: str
    color: str | None = None
    bold: bool | None = None
    marker: str | None = None    # small square before the text


CellLike = Union[str, Cell]


class Table(QWidget):
    """Painted table with fixed columns and fixed row height. Rows can never overlap or reflow."""
    PAD = 10

    def __init__(self, columns: list[Column], row_h: int = 28, header: bool = True,
                 px: int = 13, header_px: int = 11):
        super().__init__()
        self.cols, self.row_h, self.show_header, self.px, self.hpx = columns, row_h, header, px, header_px
        self.rows: list[list[CellLike]] = []
        self.hl: set[int] = set()
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self._fit()

    def set_rows(self, rows: list[list[CellLike]], highlight: set[int] | None = None):
        self.rows, self.hl = rows, highlight or set()
        self._fit()
        self.update()

    def _head_h(self) -> int:
        return 26 if self.show_header else 0

    def _fit(self):
        h = self._head_h() + max(1, len(self.rows)) * self.row_h + 1
        self.setFixedHeight(h)

    def sizeHint(self) -> QSize:
        return QSize(300, self.height())

    def minimumSizeHint(self) -> QSize:
        return QSize(120, self.height())

    def _widths(self) -> list[float]:
        avail = self.width() - 2 * self.PAD
        fixed = sum(c.w for c in self.cols if c.w)
        flex_total = sum(c.flex for c in self.cols if not c.w) or 1
        rest = max(0, avail - fixed)
        return [c.w if c.w else rest * c.flex / flex_total for c in self.cols]

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing, False)
        p.fillRect(self.rect(), T.qc(T.SHEET))
        widths = self._widths()
        y = 0.0
        if self.show_header:
            p.fillRect(QRectF(0, 0, self.width(), self._head_h()), T.qc("#E9EBED"))
            p.setFont(T.font("sans", self.hpx, "bold", 0.8))
            p.setPen(T.qc(T.MUTED))
            x = float(self.PAD)
            for c, w in zip(self.cols, widths):
                self._text(p, QRectF(x, 0, w - 8, self._head_h()), c.title.upper(), c.align)
                x += w
            p.setPen(T.qc(T.INK))
            p.drawLine(0, self._head_h() - 1, self.width(), self._head_h() - 1)
            y = self._head_h()
        if not self.rows:
            p.setFont(T.font("sans", self.px))
            p.setPen(T.qc(T.MUTED))
            self._text(p, QRectF(self.PAD, y, self.width() - 2 * self.PAD, self.row_h), "No entries.", "left")
        for i, row in enumerate(self.rows):
            if i in self.hl:
                p.fillRect(QRectF(0, y, self.width(), self.row_h), T.qc("#E3E8EF"))
            x = float(self.PAD)
            for c, w, cell in zip(self.cols, widths, row):
                cell = cell if isinstance(cell, Cell) else Cell(cell)
                bold = c.bold if cell.bold is None else cell.bold
                p.setFont(T.font("mono" if c.mono else "sans", self.px, "semibold" if bold else "regular"))
                p.setPen(T.qc(cell.color or T.INK))
                tx = x
                if cell.marker:
                    p.fillRect(QRectF(x, y + self.row_h / 2 - 4, 8, 8), T.qc(cell.marker))
                    tx += 14
                self._text(p, QRectF(tx, y, w - 8 - (tx - x), self.row_h), cell.text, c.align)
                x += w
            y += self.row_h
            p.setPen(T.qc(T.HAIR))
            p.drawLine(0, int(y) - 1, self.width(), int(y) - 1)

    @staticmethod
    def _text(p: QPainter, r: QRectF, text: str, align: str):
        fm = p.fontMetrics()
        text = fm.elidedText(text, Qt.ElideRight, int(r.width()))
        flags = Qt.AlignVCenter | (Qt.AlignRight if align == "right" else Qt.AlignLeft)
        p.drawText(r, int(flags), text)
