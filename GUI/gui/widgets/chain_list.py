from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel
from PySide6.QtCore import Qt
from ..theme import (
    INK, INK_2,
    mono_font, section_title_font
)

class ChainListWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        
        lbl_title = QLabel("Processing chain")
        lbl_title.setFont(section_title_font())
        layout.addWidget(lbl_title)
        
        chain = [
            ("Camera/OpenCV", "opened once"),
            ("YOLO/best.pt", "required"),
            ("Hands/MediaPipe", "adapter"),
            ("Shape/Boundary", "adapter"),
            ("Events/Pick, manipulate, place", ""),
            ("Steps/Checker reads the .md procedure", "")
        ]
        
        for name, note in chain:
            row = QHBoxLayout()
            lbl_name = QLabel(name)
            lbl_name.setFont(mono_font(13))
            
            lbl_note = QLabel(note)
            lbl_note.setFont(mono_font(13))
            lbl_note.setStyleSheet(f"color: {INK_2.name()};")
            
            lbl_ok = QLabel("OK")
            lbl_ok.setFont(mono_font(13))
            lbl_ok.setAlignment(Qt.AlignmentFlag.AlignRight)
            
            row.addWidget(lbl_name)
            if note:
                row.addWidget(lbl_note)
            row.addWidget(lbl_ok, 1)
            layout.addLayout(row)
