from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QFrame
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QKeySequence, QShortcut
from .theme import PAPER, INK, INK_2, INK_3, RULE_HEAVY, meta_font, mono_font
from .state import StatusSnapshot
from .mock_provider import MockProvider

from .widgets.status_bar import StatusBarWidget
from .widgets.next_step import NextStepWidget
from .widgets.procedure_list import ProcedureListWidget
from .widgets.alert_list import AlertListWidget
from .widgets.event_log import EventLogWidget
from .widgets.rack_table import RackTableWidget
from .widgets.chain_list import ChainListWidget
from .widgets.camera_view import CameraSectionWidget

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("ORBITA · SIH26174 Prototype")
        self.setMinimumSize(1280, 800)
        self.resize(1440, 900)
        
        self.provider = MockProvider()
        
        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        
        main_layout = QVBoxLayout(main_widget)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        
        # Header
        header = QWidget()
        header.setFixedHeight(60)
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(20, 10, 20, 10)
        
        lbl_title = QLabel("ORBITA")
        lbl_title.setStyleSheet("font-size: 22px; font-weight: bold;")
        lbl_sub = QLabel("BAS experiment monitor · SIH26174")
        lbl_sub.setStyleSheet(f"font-size: 14px; color: {INK_2.name()};")
        
        header_layout.addWidget(lbl_title)
        header_layout.addSpacing(8)
        header_layout.addWidget(lbl_sub)
        header_layout.addStretch()
        
        lbl_local = QLabel("Local only")
        lbl_local.setFont(meta_font())
        lbl_rec = QLabel("Recording")
        lbl_rec.setFont(meta_font())
        lbl_lan = QLabel("LAN stream off")
        lbl_lan.setFont(meta_font())
        
        self.btn_voice = QPushButton("Voice on")
        self.btn_voice.setCheckable(True)
        self.btn_voice.setFont(meta_font())
        self.btn_voice.setStyleSheet(f"border: 1px solid {INK.name()}; padding: 4px 8px;")
        self.btn_voice.setToolTip("Toggle voice (M)")
        self.btn_voice.toggled.connect(self.provider.set_voice_muted)
        
        header_layout.addWidget(lbl_local)
        header_layout.addSpacing(16)
        header_layout.addWidget(lbl_rec)
        header_layout.addSpacing(16)
        header_layout.addWidget(lbl_lan)
        header_layout.addSpacing(16)
        header_layout.addWidget(self.btn_voice)
        header_layout.addStretch()
        
        lbl_demo = QLabel("Demo build, not flight software")
        lbl_demo.setFont(meta_font())
        lbl_demo.setStyleSheet(f"color: {INK_2.name()};")
        
        lbl_met_lbl = QLabel("MET")
        lbl_met_lbl.setFont(meta_font())
        
        self.lbl_met_val = QLabel("00:00:00")
        self.lbl_met_val.setFont(mono_font(22))
        
        header_layout.addWidget(lbl_demo)
        header_layout.addSpacing(24)
        header_layout.addWidget(lbl_met_lbl)
        header_layout.addSpacing(8)
        header_layout.addWidget(self.lbl_met_val)
        
        main_layout.addWidget(header)
        
        # Rule under header
        rule = QWidget()
        rule.setFixedHeight(2)
        rule.setStyleSheet(f"background-color: {RULE_HEAVY.name()};")
        main_layout.addWidget(rule)
        
        # Status Bar
        self.status_bar = StatusBarWidget()
        main_layout.addWidget(self.status_bar)
        
        # Main Body (2 columns)
        body = QWidget()
        body_layout = QHBoxLayout(body)
        body_layout.setContentsMargins(20, 20, 20, 20)
        body_layout.setSpacing(40)
        
        # Left column
        left_col = QWidget()
        left_layout = QVBoxLayout(left_col)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(24)
        
        self.camera_sec = CameraSectionWidget(self.provider)
        left_layout.addWidget(self.camera_sec)
        
        self.rack_table = RackTableWidget()
        left_layout.addWidget(self.rack_table)
        
        self.chain_list = ChainListWidget()
        left_layout.addWidget(self.chain_list)
        left_layout.addStretch()
        
        body_layout.addWidget(left_col, 1) # flexible
        
        # Right column
        right_col = QWidget()
        right_col.setMinimumWidth(400)
        right_col.setMaximumWidth(600)
        right_layout = QVBoxLayout(right_col)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(24)
        
        self.next_step = NextStepWidget()
        right_layout.addWidget(self.next_step)
        
        self.proc_list = ProcedureListWidget()
        right_layout.addWidget(self.proc_list)
        
        self.alert_list = AlertListWidget()
        right_layout.addWidget(self.alert_list, 1) # flexible
        
        body_layout.addWidget(right_col)
        main_layout.addWidget(body, 1) # flex body
        
        # Event log
        self.event_log = EventLogWidget()
        main_layout.addWidget(self.event_log)
        
        # Footer
        footer = QWidget()
        footer_layout = QHBoxLayout(footer)
        footer_layout.setContentsMargins(20, 10, 20, 10)
        lbl_foot = QLabel("Rack-relative means measured against main_box on a ground demo setup, not a calibrated spacecraft frame. All values are sample data. Accuracy, frame rate and per-module timing have not been measured.")
        lbl_foot.setFont(meta_font())
        lbl_foot.setStyleSheet(f"color: {INK_3.name()}; font-size: 12px;")
        lbl_foot.setWordWrap(True)
        footer_layout.addWidget(lbl_foot)
        main_layout.addWidget(footer)
        
        # Background
        self.setStyleSheet(f"QMainWindow {{ background-color: {PAPER.name()}; }} QWidget {{ color: {INK.name()}; }}")
        
        # Bindings
        self.provider.add_listener(self.update_from_snapshot)
        
        QShortcut(QKeySequence("1"), self).activated.connect(lambda: self.provider.set_trial("Correct run"))
        QShortcut(QKeySequence("2"), self).activated.connect(lambda: self.provider.set_trial("Skipped step"))
        QShortcut(QKeySequence("3"), self).activated.connect(lambda: self.provider.set_trial("Wrong order"))
        QShortcut(QKeySequence("R"), self).activated.connect(self.cycle_rotation)
        QShortcut(QKeySequence("M"), self).activated.connect(self.toggle_voice)
        
        # Init
        self.provider.emit()

    def update_from_snapshot(self, snap: StatusSnapshot):
        self.lbl_met_val.setText(snap.met)
        if snap.voice_muted:
            self.btn_voice.setText("Voice muted")
            self.btn_voice.setChecked(True)
        else:
            self.btn_voice.setText("Voice on")
            self.btn_voice.setChecked(False)
            
        self.status_bar.update_from_snapshot(snap)
        self.camera_sec.update_from_snapshot(snap)
        self.rack_table.update_from_snapshot(snap)
        self.next_step.update_from_snapshot(snap)
        self.proc_list.update_from_snapshot(snap)
        self.alert_list.update_from_snapshot(snap)
        self.event_log.update_from_snapshot(snap)

    def cycle_rotation(self):
        rots = [0, 90, 180, 270]
        cur = self.provider.rotation
        self.provider.set_rotation(rots[(rots.index(cur) + 1) % 4])
        
    def toggle_voice(self):
        self.provider.set_voice_muted(not self.provider.voice_muted)
