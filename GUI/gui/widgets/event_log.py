from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QScrollArea, QFrame, QGridLayout
from PySide6.QtCore import Qt
from ..theme import (
    INK, INK_2, INK_3, BLUE, AMBER_TEXT, RED_TEXT, RULE_LIGHT,
    mono_font, section_title_font, meta_font
)
from ..state import StatusSnapshot

class EventLogWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        
        header = QHBoxLayout()
        lbl_title = QLabel("Event log")
        lbl_title.setFont(section_title_font())
        lbl_meta = QLabel("logs/20261005_0942_events.jsonl · newest first")
        lbl_meta.setFont(meta_font())
        lbl_meta.setStyleSheet(f"color: {INK_2.name()};")
        header.addWidget(lbl_title)
        header.addStretch()
        header.addWidget(lbl_meta)
        layout.addLayout(header)
        
        # Header row
        grid = QGridLayout()
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setHorizontalSpacing(16)
        
        headers = ["Time", "Level", "Event", "Detail", "Conf."]
        for i, h in enumerate(headers):
            lbl = QLabel(h)
            lbl.setFont(meta_font())
            lbl.setStyleSheet("font-weight: bold;")
            grid.addWidget(lbl, 0, i)
            
        layout.addLayout(grid)
        
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.scroll.setStyleSheet("background: transparent;")
        self.scroll.setMaximumHeight(240)
        
        self.content = QWidget()
        self.grid_layout = QGridLayout(self.content)
        self.grid_layout.setContentsMargins(0, 0, 0, 0)
        self.grid_layout.setHorizontalSpacing(16)
        self.grid_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        
        self.scroll.setWidget(self.content)
        layout.addWidget(self.scroll)

    def update_from_snapshot(self, snap: StatusSnapshot):
        while self.grid_layout.count():
            item = self.grid_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
                
        row = 0
        for ev in snap.events:
            color = INK
            if ev.level == "caution":
                color = AMBER_TEXT
            elif ev.level == "warning":
                color = RED_TEXT
            elif ev.level == "voice":
                color = BLUE
            elif ev.level in ("info", "event", "step"):
                if ev.level == "info":
                    color = INK_3
            
            f = mono_font(13)
            
            lbl_time = QLabel(ev.time)
            lbl_time.setFont(f)
            lbl_time.setStyleSheet(f"color: {color.name()};")
            
            lbl_level = QLabel(ev.level)
            lbl_level.setFont(f)
            lbl_level.setStyleSheet(f"color: {color.name()};")
            
            lbl_event = QLabel(ev.event)
            lbl_event.setFont(f)
            lbl_event.setStyleSheet(f"color: {color.name()};")
            
            lbl_detail = QLabel(ev.detail)
            lbl_detail.setFont(f)
            lbl_detail.setStyleSheet(f"color: {color.name()};")
            lbl_detail.setWordWrap(True)
            
            lbl_conf = QLabel(ev.conf)
            lbl_conf.setFont(f)
            lbl_conf.setStyleSheet(f"color: {color.name()};")
            
            self.grid_layout.addWidget(lbl_time, row, 0)
            self.grid_layout.addWidget(lbl_level, row, 1)
            self.grid_layout.addWidget(lbl_event, row, 2)
            self.grid_layout.addWidget(lbl_detail, row, 3)
            self.grid_layout.addWidget(lbl_conf, row, 4)
            
            row += 1
