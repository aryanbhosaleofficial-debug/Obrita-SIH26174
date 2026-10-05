from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame
from PySide6.QtCore import Qt, QRect, QPoint
from PySide6.QtGui import QPainter, QPen, QColor, QFontMetrics, QPalette
from ..theme import (
    INK, INK_2, BLUE, AMBER_TEXT, RED_TEXT,
    ROW_ACTIVE, ROW_SKIPPED, ROW_WRONG, PAPER,
    mono_font, body_font, section_title_font, meta_font
)
from ..state import StatusSnapshot

class CheckboxGlyph(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(18, 18)
        self.status = "pending"
        
    def set_status(self, status):
        self.status = status
        self.update()
        
    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect = self.rect()
        
        if self.status == "done":
            p.fillRect(rect, INK)
            p.setPen(QPen(QColor("white"), 2))
            p.drawLine(4, 9, 8, 13)
            p.drawLine(8, 13, 14, 5)
        elif self.status == "active":
            p.fillRect(rect, QColor("white"))
            p.setPen(QPen(BLUE, 2))
            p.drawRect(rect.adjusted(1, 1, -1, -1))
            p.setBrush(BLUE)
            p.setPen(Qt.PenStyle.NoPen)
            p.drawEllipse(QPoint(9, 9), 4, 4)
        elif self.status == "skipped":
            p.fillRect(rect, QColor("#E39A00"))
            p.setPen(QPen(INK, 2))
            p.drawLine(4, 9, 14, 9)
        elif self.status == "wrong":
            p.fillRect(rect, QColor("#D7301F"))
            p.setPen(QPen(QColor("white"), 2))
            p.drawLine(5, 5, 13, 13)
            p.drawLine(13, 5, 5, 13)
        else:
            p.setPen(QPen(QColor("#888888"), 1))
            p.drawRect(rect.adjusted(0, 0, -1, -1))

class ProcedureRow(QFrame):
    def __init__(self, step_num, parent=None):
        super().__init__(parent)
        self.step_num = step_num
        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        
        self.glyph = CheckboxGlyph()
        layout.addWidget(self.glyph)
        
        self.lbl_num = QLabel(f"{step_num:02d}")
        self.lbl_num.setFont(mono_font(14))
        layout.addWidget(self.lbl_num)
        
        text_layout = QVBoxLayout()
        text_layout.setSpacing(2)
        self.lbl_name = QLabel()
        self.lbl_name.setFont(body_font())
        self.lbl_id = QLabel()
        self.lbl_id.setFont(mono_font(12))
        self.lbl_id.setStyleSheet(f"color: {INK_2.name()};")
        text_layout.addWidget(self.lbl_name)
        text_layout.addWidget(self.lbl_id)
        layout.addLayout(text_layout, 1)
        
        self.lbl_state = QLabel()
        self.lbl_state.setFont(mono_font(12))
        self.lbl_state.setAlignment(Qt.AlignmentFlag.AlignRight)
        layout.addWidget(self.lbl_state)
        
    def update_step(self, step):
        self.lbl_name.setText(step.name)
        self.lbl_id.setText(step.id)
        self.lbl_state.setText(f"{step.status} {step.time}")
        self.glyph.set_status(step.status)
        
        self.setAutoFillBackground(True)
        pal = self.palette()
        if step.status == "active":
            pal.setColor(QPalette.ColorRole.Window, ROW_ACTIVE)
            self.lbl_state.setStyleSheet(f"color: {BLUE.name()};")
        elif step.status == "skipped":
            pal.setColor(QPalette.ColorRole.Window, ROW_SKIPPED)
            self.lbl_state.setStyleSheet(f"color: {AMBER_TEXT.name()};")
        elif step.status == "wrong":
            pal.setColor(QPalette.ColorRole.Window, ROW_WRONG)
            self.lbl_state.setStyleSheet(f"color: {RED_TEXT.name()};")
        else:
            pal.setColor(QPalette.ColorRole.Window, PAPER)
            self.lbl_state.setStyleSheet(f"color: {INK_2.name()};")
        self.setPalette(pal)

class ProcedureListWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        
        header = QHBoxLayout()
        lbl_title = QLabel("Procedure")
        lbl_title.setFont(section_title_font())
        lbl_meta = QLabel("red_yellow_box.md · example steps")
        lbl_meta.setFont(meta_font())
        lbl_meta.setStyleSheet(f"color: {INK_2.name()};")
        header.addWidget(lbl_title)
        header.addStretch()
        header.addWidget(lbl_meta)
        layout.addLayout(header)
        
        self.rows = []
        for i in range(1, 6):
            row = ProcedureRow(i)
            self.rows.append(row)
            layout.addWidget(row)
            
    def update_from_snapshot(self, snap: StatusSnapshot):
        for i, step in enumerate(snap.steps):
            if i < len(self.rows):
                self.rows[i].update_step(step)
