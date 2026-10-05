from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QButtonGroup
from PySide6.QtCore import Qt, QTimer, QPropertyAnimation, QEasingCurve, QPoint
from PySide6.QtGui import QPainter, QColor, QPen, QBrush, QFont, QRadialGradient, QLinearGradient
from ..theme import INK, INK_2, BLUE, RULE_HEAVY, mono_font, section_title_font, meta_font
from ..state import StatusSnapshot

class CameraCanvas(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumHeight(400)
        self.rotation_deg = 0
        self.target_rotation = 0
        self.anim = None
        self.snap = None
        
    def set_snapshot(self, snap: StatusSnapshot):
        self.snap = snap
        if self.target_rotation != snap.rotation_deg:
            self.target_rotation = snap.rotation_deg
            self.anim = QPropertyAnimation(self, b"rotation_deg_prop")
            self.anim.setDuration(400)
            self.anim.setStartValue(self.rotation_deg)
            # handle shortest path for rotation
            diff = (self.target_rotation - self.rotation_deg) % 360
            if diff > 180:
                diff -= 360
            self.anim.setEndValue(self.rotation_deg + diff)
            self.anim.setEasingCurve(QEasingCurve.Type.InOutQuad)
            self.anim.start()
        else:
            self.update()
            
    def get_rotation(self):
        return self.rotation_deg
        
    def set_rotation(self, val):
        self.rotation_deg = val
        self.update()
        
    from PySide6.QtCore import Property
    rotation_deg_prop = Property(float, get_rotation, set_rotation)

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.fillRect(self.rect(), QColor("#1B1B1D"))
        
        # 16:9 box
        w = self.width()
        h = int(w * 9 / 16)
        if h > self.height():
            h = self.height()
            w = int(h * 16 / 9)
            
        x_off = (self.width() - w) // 2
        y_off = (self.height() - h) // 2
        
        p.translate(x_off, y_off)
        
        # Vignette
        grad = QRadialGradient(w/2, h/2, w/1.5)
        grad.setColorAt(0, QColor("#3A3A3C"))
        grad.setColorAt(0.5, QColor("#262628"))
        grad.setColorAt(1, QColor("#1B1B1D"))
        p.fillRect(0, 0, w, h, grad)
        
        # HUD layer (non-rotating)
        p.setPen(QColor("white"))
        p.setFont(mono_font(12))
        
        frame_time = self.snap.frame_time if self.snap else "T+00:00:00"
        p.drawText(10, 20, f"CAM 0 · {frame_time}")
        
        # right top
        p.drawText(w - 150, 20, "↑ Camera up not used")
        
        # left bottom
        rot_deg = self.target_rotation % 360
        p.drawText(10, h - 10, f"Setup rotation {rot_deg}°")
        
        # right bottom
        p.drawText(w - 130, h - 10, "3 objects · 1 hand")
        
        # Viewfinder marks
        vl = 20
        p.drawLine(10, 30, 10, 30+vl)
        p.drawLine(10, 30, 10+vl, 30)
        p.drawLine(w-10, 30, w-10, 30+vl)
        p.drawLine(w-10, 30, w-10-vl, 30)
        p.drawLine(10, h-30, 10, h-30-vl)
        p.drawLine(10, h-30, 10+vl, h-30)
        p.drawLine(w-10, h-30, w-10, h-30-vl)
        p.drawLine(w-10, h-30, w-10-vl, h-30)

        # Scene layer (rotating)
        p.translate(w/2, h/2)
        p.rotate(self.rotation_deg)
        p.translate(-w/2, -h/2)
        
        def draw_box(cx_pct, cy_pct, w_pct, h_pct, color, label, conf, outline_dash=False, tab_above=True):
            cx, cy = w * cx_pct, h * cy_pct
            bw, bh = w * w_pct, h * h_pct
            
            p.setBrush(color if color else Qt.BrushStyle.NoBrush)
            if outline_dash:
                pen = QPen(QColor("#F2F2F0"), 1)
                pen.setDashPattern([4, 4])
                p.setPen(pen)
            else:
                p.setPen(Qt.PenStyle.NoPen)
                
            p.drawRect(cx - bw/2, cy - bh/2, bw, bh)
            
            if not outline_dash:
                p.setBrush(Qt.BrushStyle.NoBrush)
                p.setPen(QPen(QColor("#F2F2F0"), 1))
                p.drawRect(cx - bw/2 - 4, cy - bh/2 - 4, bw + 8, bh + 8)
                
            # Tab
            p.save()
            tw, th = 90, 16
            tx = cx - bw/2
            ty = (cy - bh/2 - 20) if tab_above else (cy + bh/2 + 6)
            
            p.translate(tx + tw/2, ty + th/2)
            p.rotate(-self.rotation_deg)
            p.translate(-(tx + tw/2), -(ty + th/2))
            
            p.setBrush(QColor("#F2F2F0") if color else Qt.BrushStyle.NoBrush)
            p.setPen(QColor(INK) if color else QColor("#F2F2F0"))
            p.setFont(mono_font(10))
            if color:
                p.drawRect(tx, ty, tw, th)
            p.drawText(tx + 4, ty + 12, f"{label} {conf}")
            p.restore()

        # main_box
        draw_box(0.50, 0.50, 0.24, 0.30, None, "main_box", "0.97", outline_dash=True)
        
        # rack axes
        rx, ry = w * 0.36, h * 0.32
        al = w * 0.12
        p.setPen(QPen(QColor("#F2F2F0"), 1))
        p.drawLine(rx, ry, rx + al, ry)
        
        pen = QPen(QColor("#F2F2F0"), 1)
        pen.setDashPattern([4, 4])
        p.setPen(pen)
        p.drawLine(rx, ry, rx, ry + al)
        
        p.save()
        p.translate(rx + al + 10, ry + 4)
        p.rotate(-self.rotation_deg)
        p.drawText(0, 0, "+X")
        p.restore()
        
        p.save()
        p.translate(rx - 4, ry + al + 14)
        p.rotate(-self.rotation_deg)
        p.drawText(0, 0, "+Y")
        p.restore()
        
        # red_box
        draw_box(0.32, 0.338, 0.10, 0.14, QColor("#A94437"), "red_box", "0.93")
        
        # yellow_box
        conf = "0.88"
        if self.snap:
            for ev in self.snap.events:
                if "yellow_box" in ev.detail and ev.conf:
                    conf = ev.conf
                    break
        draw_box(0.673, 0.645, 0.10, 0.14, QColor("#C9A431"), "yellow_box", conf, tab_above=False)
        
        # hand
        hx1, hy1 = w * 0.632, h * 0.585
        hx2, hy2 = w * 0.590, h * 0.640
        p.setPen(QPen(QColor("white"), 1.5))
        p.drawLine(hx1, hy1, hx2, hy2)
        
        p.setBrush(QColor("white"))
        p.setPen(Qt.PenStyle.NoPen)
        p.drawEllipse(QPoint(int(hx1), int(hy1)), 5, 5)
        p.drawEllipse(QPoint(int(hx2), int(hy2)), 4, 4)
        
        p.save()
        hx = hx1 + 10
        hy = hy1 - 10
        p.translate(hx + 40, hy + 8)
        p.rotate(-self.rotation_deg)
        p.translate(-(hx + 40), -(hy + 8))
        
        p.setBrush(QColor("white"))
        p.setPen(INK)
        p.drawRect(hx, hy, 70, 16)
        p.drawText(hx + 4, hy + 12, "hand 0.81")
        p.restore()

class CameraSectionWidget(QWidget):
    def __init__(self, provider, parent=None):
        super().__init__(parent)
        self.provider = provider
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        
        header = QHBoxLayout()
        lbl_title = QLabel("Camera 0")
        lbl_title.setFont(section_title_font())
        lbl_meta = QLabel("Simulated scene")
        lbl_meta.setFont(meta_font())
        lbl_meta.setStyleSheet(f"color: {INK_2.name()};")
        header.addWidget(lbl_title)
        header.addStretch()
        header.addWidget(lbl_meta)
        
        top_line = QWidget()
        top_line.setFixedHeight(2)
        top_line.setStyleSheet(f"background-color: {RULE_HEAVY.name()};")
        
        layout.addWidget(top_line)
        layout.addLayout(header)
        
        self.canvas = CameraCanvas()
        layout.addWidget(self.canvas)
        
        # Controls
        ctrl_layout = QHBoxLayout()
        
        def create_segmented(items, cb):
            w = QWidget()
            l = QHBoxLayout(w)
            l.setContentsMargins(0, 0, 0, 0)
            l.setSpacing(0)
            bg = QButtonGroup(w)
            btns = []
            for i, txt in enumerate(items):
                b = QPushButton(txt)
                b.setCheckable(True)
                b.setFont(mono_font(12))
                style = f"""
                QPushButton {{
                    border: 1px solid {INK.name()};
                    background: transparent;
                    color: {INK.name()};
                    padding: 4px 8px;
                }}
                QPushButton:checked {{
                    background: {INK.name()};
                    color: white;
                }}
                """
                if i == 0:
                    b.setChecked(True)
                b.setStyleSheet(style)
                bg.addButton(b, i)
                l.addWidget(b)
                btns.append(b)
            bg.idClicked.connect(cb)
            return w, btns
            
        self.trial_w, self.trial_btns = create_segmented(["Correct run", "Skipped step", "Wrong order"], 
            lambda id: self.provider.set_trial(["Correct run", "Skipped step", "Wrong order"][id]))
            
        self.rot_w, self.rot_btns = create_segmented(["0°", "90°", "180°", "270°"],
            lambda id: self.provider.set_rotation([0, 90, 180, 270][id]))
            
        ctrl_layout.addWidget(QLabel("Trial (simulation):"))
        ctrl_layout.addWidget(self.trial_w)
        ctrl_layout.addSpacing(20)
        ctrl_layout.addWidget(QLabel("Setup rotation:"))
        ctrl_layout.addWidget(self.rot_w)
        ctrl_layout.addStretch()
        
        layout.addLayout(ctrl_layout)

    def update_from_snapshot(self, snap: StatusSnapshot):
        self.canvas.set_snapshot(snap)
        
        # Update btn states
        trials = ["Correct run", "Skipped step", "Wrong order"]
        rots = [0, 90, 180, 270]
        
        if snap.trial_name in trials:
            self.trial_btns[trials.index(snap.trial_name)].setChecked(True)
            
        if snap.rotation_deg in rots:
            self.rot_btns[rots.index(snap.rotation_deg)].setChecked(True)
