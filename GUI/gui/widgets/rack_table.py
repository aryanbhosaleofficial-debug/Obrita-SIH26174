from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QGridLayout
from PySide6.QtCore import Qt
from ..theme import (
    INK, INK_2, RULE_LIGHT,
    mono_font, section_title_font, meta_font
)
from ..state import StatusSnapshot

class RackTableWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        
        header = QHBoxLayout()
        lbl_title = QLabel("Position in the rack frame")
        lbl_title.setFont(section_title_font())
        lbl_meta = QLabel("Units of main_box width. Unchanged when the setup is rotated.")
        lbl_meta.setFont(meta_font())
        lbl_meta.setStyleSheet(f"color: {INK_2.name()};")
        header.addWidget(lbl_title)
        header.addStretch()
        header.addWidget(lbl_meta)
        layout.addLayout(header)
        
        grid = QGridLayout()
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setHorizontalSpacing(16)
        grid.setVerticalSpacing(4)
        
        headers = ["Object", "X", "Y", "Aspect", "Conf."]
        for i, h in enumerate(headers):
            lbl = QLabel(h)
            lbl.setFont(meta_font())
            lbl.setStyleSheet("font-weight: bold;")
            grid.addWidget(lbl, 0, i)
            
        rows = [
            ("red_box", "-0.75", "-0.38", "1.27", "0.93"),
            ("yellow_box", "0.72", "0.34", "1.27", "0.88"), # will be updated from conf
            ("hand, index tip", "0.55", "0.20", "—", "0.81")
        ]
        
        self.conf_lbl = QLabel()
        self.conf_lbl.setFont(mono_font(13))
        
        for r_idx, r_data in enumerate(rows, 1):
            for c_idx, text in enumerate(r_data):
                lbl = QLabel(text)
                lbl.setFont(mono_font(13))
                if r_idx == 2 and c_idx == 4:
                    self.conf_lbl = lbl
                grid.addWidget(lbl, r_idx, c_idx)
                
        layout.addLayout(grid)

    def update_from_snapshot(self, snap: StatusSnapshot):
        conf = ""
        for ev in snap.events:
            if "yellow_box" in ev.detail and ev.conf:
                conf = ev.conf
                break
        self.conf_lbl.setText(conf)
