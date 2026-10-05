from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame
)
from PySide6.QtCore import Qt
from ..theme import (
    INK, INK_2, INK_3, BLUE, AMBER_TEXT, RED_TEXT, BAR_TRACK,
    key_text_font, mono_font, section_title_font, meta_font
)
from ..state import StatusSnapshot

class NextStepWidget(QFrame):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFrameShape(QFrame.Shape.NoFrame)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)
        
        self.lbl_title = QLabel("Next step")
        self.lbl_title.setFont(section_title_font())
        layout.addWidget(self.lbl_title)
        
        step_layout = QHBoxLayout()
        self.lbl_num = QLabel("03")
        self.lbl_num.setFont(mono_font(22))
        self.lbl_text = QLabel("Pick up the yellow box")
        self.lbl_text.setFont(key_text_font())
        self.lbl_text.setStyleSheet("font-weight: 600;") # semibold
        step_layout.addWidget(self.lbl_num)
        step_layout.addWidget(self.lbl_text, 1)
        layout.addLayout(step_layout)
        
        self.lbl_note = QLabel("Note")
        self.lbl_note.setFont(meta_font())
        self.lbl_note.setStyleSheet(f"color: {INK_2.name()};")
        layout.addWidget(self.lbl_note)
        
        prog_layout = QHBoxLayout()
        self.lbl_prog_text = QLabel("PICK yellow_box")
        self.lbl_prog_text.setFont(mono_font(12))
        self.lbl_conf = QLabel("conf.")
        self.lbl_conf.setFont(mono_font(12))
        prog_layout.addWidget(self.lbl_prog_text, 1)
        prog_layout.addWidget(self.lbl_conf)
        layout.addLayout(prog_layout)
        
        self.prog_bar = QWidget()
        self.prog_bar.setFixedHeight(6)
        layout.addWidget(self.prog_bar)
        
        self.pct = 0

    def update_from_snapshot(self, snap: StatusSnapshot):
        ns = snap.next_step
        self.lbl_title.setText(ns.title)
        self.lbl_num.setText(ns.step_num)
        self.lbl_text.setText(snap.steps[int(ns.step_num)-1].name if ns.step_num.isdigit() else "")
        self.lbl_note.setText(ns.note)
        self.lbl_prog_text.setText(ns.progress_text)
        self.lbl_conf.setText(f"conf. {ns.conf}" if ns.conf else "")
        self.pct = ns.progress_pct
        self.prog_bar.update()
        
    def paintEvent(self, event):
        super().paintEvent(event)
        from PySide6.QtGui import QPainter
        p = QPainter(self)
        p.fillRect(self.prog_bar.geometry(), BAR_TRACK)
        fill_rect = self.prog_bar.geometry()
        fill_rect.setWidth(int(fill_rect.width() * (self.pct / 100.0)))
        p.fillRect(fill_rect, BLUE)
