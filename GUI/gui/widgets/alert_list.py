from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QScrollArea, QFrame
from PySide6.QtCore import Qt
from ..theme import (
    INK, INK_2, INK_3, BLUE, AMBER_TEXT, RED_TEXT, RULE_LIGHT,
    mono_font, section_title_font, meta_font
)
from ..state import StatusSnapshot

class AlertListWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        
        header = QHBoxLayout()
        lbl_title = QLabel("Alerts")
        lbl_title.setFont(section_title_font())
        lbl_meta = QLabel("Only the step checker raises voice alerts.")
        lbl_meta.setFont(meta_font())
        lbl_meta.setStyleSheet(f"color: {INK_2.name()};")
        header.addWidget(lbl_title)
        header.addStretch()
        header.addWidget(lbl_meta)
        layout.addLayout(header)
        
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.scroll.setStyleSheet("background: transparent;")
        
        self.content = QWidget()
        self.content_layout = QVBoxLayout(self.content)
        self.content_layout.setContentsMargins(0, 0, 0, 0)
        self.content_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        
        self.scroll.setWidget(self.content)
        layout.addWidget(self.scroll)

    def update_from_snapshot(self, snap: StatusSnapshot):
        while self.content_layout.count():
            item = self.content_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
                
        for alert in snap.alerts:
            row = QHBoxLayout()
            lbl_time = QLabel(f"T+{alert.time}")
            lbl_time.setFont(mono_font(12))
            
            lbl_level = QLabel(alert.level)
            lbl_level.setFont(meta_font())
            lbl_level.setStyleSheet("font-weight: bold;")
            
            lbl_msg = QLabel(alert.message)
            lbl_msg.setFont(meta_font())
            lbl_msg.setWordWrap(True)
            
            if alert.level == "Advisory":
                lbl_level.setStyleSheet(f"color: {BLUE.name()}; font-weight: bold;")
            elif alert.level == "Caution":
                lbl_level.setStyleSheet(f"color: {AMBER_TEXT.name()}; font-weight: bold;")
            elif alert.level == "Warning":
                lbl_level.setStyleSheet(f"color: {RED_TEXT.name()}; font-weight: bold;")
                
            row.addWidget(lbl_time)
            row.addWidget(lbl_level)
            row.addWidget(lbl_msg, 1)
            
            w = QWidget()
            w.setLayout(row)
            self.content_layout.addWidget(w)
