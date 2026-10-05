from PySide6.QtWidgets import QWidget, QHBoxLayout, QLabel
from PySide6.QtCore import Qt
from PySide6.QtGui import QPalette, QColor
from ..theme import (
    NOMINAL_STATUS_BAR, AMBER, RED, INK, 
    key_text_font, mono_font, meta_font
)
from ..state import StatusSnapshot

class StatusBarWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(48)
        self.setAutoFillBackground(True)
        
        layout = QHBoxLayout(self)
        layout.setContentsMargins(20, 0, 20, 0)
        
        self.lbl_level = QLabel("Nominal")
        self.lbl_level.setFont(key_text_font())
        self.lbl_level.setStyleSheet("font-weight: bold;")
        
        self.lbl_message = QLabel("Message")
        self.lbl_message.setFont(key_text_font())
        self.lbl_message.setWordWrap(True)
        
        self.lbl_voice = QLabel("Voice: \"\"")
        self.lbl_voice.setFont(mono_font(12))
        self.lbl_voice.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        
        layout.addWidget(self.lbl_level)
        layout.addSpacing(16)
        layout.addWidget(self.lbl_message, 1)
        layout.addWidget(self.lbl_voice)

    def update_from_snapshot(self, snap: StatusSnapshot):
        self.lbl_level.setText(snap.status_level)
        self.lbl_message.setText(snap.status_message)
        
        if snap.voice_muted:
            self.lbl_voice.setText("Voice muted, logged only")
        else:
            self.lbl_voice.setText(f'Voice: "{snap.spoken_text}"')
        
        palette = self.palette()
        if snap.status_level == "Nominal":
            palette.setColor(QPalette.ColorRole.Window, NOMINAL_STATUS_BAR)
            palette.setColor(QPalette.ColorRole.WindowText, INK)
            self.lbl_level.setStyleSheet("color: #11151A; font-weight: bold;")
            self.lbl_message.setStyleSheet("color: #11151A;")
            self.lbl_voice.setStyleSheet("color: #11151A;")
        elif snap.status_level == "Caution":
            palette.setColor(QPalette.ColorRole.Window, AMBER)
            palette.setColor(QPalette.ColorRole.WindowText, INK)
            self.lbl_level.setStyleSheet("color: #11151A; font-weight: bold;")
            self.lbl_message.setStyleSheet("color: #11151A;")
            self.lbl_voice.setStyleSheet("color: #11151A;")
        elif snap.status_level == "Warning":
            palette.setColor(QPalette.ColorRole.Window, RED)
            palette.setColor(QPalette.ColorRole.WindowText, QColor("white"))
            self.lbl_level.setStyleSheet("color: white; font-weight: bold;")
            self.lbl_message.setStyleSheet("color: white;")
            self.lbl_voice.setStyleSheet("color: white;")
            
        self.setPalette(palette)
