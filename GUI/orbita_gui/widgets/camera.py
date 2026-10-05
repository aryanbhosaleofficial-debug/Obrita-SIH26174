from __future__ import annotations
import math, random
from PySide6.QtCore import Qt, QPointF, QRectF
from PySide6.QtGui import (QPainter, QPolygonF, QColor, QPen, QBrush, QImage, QLinearGradient,
                           QRadialGradient, QPixmap, QTransform)
from PySide6.QtWidgets import QWidget, QSizePolicy
from .. import theme as T
from ..state import Scene, Detection


def _noise_tile() -> QPixmap:
    rnd = random.Random(7)
    img = QImage(128, 128, QImage.Format_ARGB32)
    img.fill(Qt.transparent)
    for _ in range(900):
        v = rnd.choice((0, 255))
        img.setPixelColor(rnd.randrange(128), rnd.randrange(128), QColor(v, v, v, 14))
    return QPixmap.fromImage(img)


class CameraView(QWidget):
    """16:9 camera pane. Shows a real frame via set_frame(), or a simulated rack scene when None.

    Overlays use normalised coordinates, so the same code draws over real video.
    """
    ASPECT = 16 / 9

    def __init__(self):
        super().__init__()
        self.frame: QImage | None = None
        self.scene = Scene()
        self.stamp = "00:00:00.000"
        self.cam_label = "CAM 0"
        self.n_objects = 0
        self.n_hands = 0
        self._noise = _noise_tile()
        self._placed: list[QRectF] = []
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.setMinimumWidth(320)
        self._fit(640)

    # ---- API
    def set_frame(self, img: QImage | None):
        self.frame = img
        self.update()

    def set_scene(self, scene: Scene, stamp: str):
        self.scene, self.stamp = scene, stamp
        self.n_objects = len(scene.objects) + (1 if scene.main_box else 0)
        self.n_hands = len(scene.hands)
        self.update()

    # ---- sizing: height always follows width (16:9), so nothing can squash or overlap it
    def _fit(self, w: int):
        h = round(w / self.ASPECT)
        if self.height() != h:
            self.setFixedHeight(h)

    def resizeEvent(self, e):
        self._fit(e.size().width())
        super().resizeEvent(e)

    # ---- painting
    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHints(QPainter.Antialiasing | QPainter.TextAntialiasing | QPainter.SmoothPixmapTransform)
        r = QRectF(self.rect())
        p.setClipRect(r)
        real = self.frame is not None and not self.frame.isNull()
        self._placed = []
        if real:
            self._draw_frame(p, r)
        else:
            self._draw_sim(p, r)
        self._draw_overlay(p, r, real)
        self._draw_finish(p, r)
        self._draw_hud(p, r)

    def _draw_frame(self, p: QPainter, r: QRectF):
        img = self.frame
        s = max(r.width() / img.width(), r.height() / img.height())      # cover
        w, h = img.width() * s, img.height() * s
        p.drawImage(QRectF(r.center().x() - w / 2, r.center().y() - h / 2, w, h), img)

    # simulated scene -----------------------------------------------------------------
    def _xf(self, r: QRectF):
        rot = self.scene.rotation % 360
        s = 0.78 if rot in (90, 270) else 1.0
        t = QTransform()
        t.translate(r.center().x(), r.center().y())
        t.rotate(rot)
        t.scale(s, s)
        t.translate(-r.center().x(), -r.center().y())
        return t

    def _draw_sim(self, p: QPainter, r: QRectF):
        g = QLinearGradient(r.topLeft(), r.bottomRight())
        g.setColorAt(0, T.qc("#363B40"))
        g.setColorAt(1, T.qc("#25292D"))
        p.fillRect(r, g)
        p.save()
        p.setTransform(self._xf(r), True)
        panel = QRectF(r.width() * 0.07, r.height() * 0.09, r.width() * 0.86, r.height() * 0.82)
        p.fillRect(panel, T.qc("#4A5158"))
        p.setPen(QPen(T.qc("#5B636B"), 1))
        for i in range(1, 10):
            x = panel.left() + panel.width() * i / 10
            p.drawLine(QPointF(x, panel.top()), QPointF(x, panel.bottom()))
        for i in range(1, 6):
            y = panel.top() + panel.height() * i / 6
            p.drawLine(QPointF(panel.left(), y), QPointF(panel.right(), y))
        p.setPen(QPen(T.qc("#6B747C"), 2))
        p.drawRect(panel)
        for d in self.scene.objects:
            if d.color:
                p.setPen(Qt.NoPen)
                p.setBrush(T.qc(d.color))
                p.drawRect(self._rect(d, r))
                p.setBrush(T.qc("#FFFFFF", 36))
                rr = self._rect(d, r)
                p.drawRect(QRectF(rr.left(), rr.top(), rr.width(), rr.height() * 0.18))
        p.restore()

    # overlays ------------------------------------------------------------------------
    @staticmethod
    def _rect(d: Detection, r: QRectF) -> QRectF:
        return QRectF((d.cx - d.w / 2) * r.width(), (d.cy - d.h / 2) * r.height(),
                      d.w * r.width(), d.h * r.height())

    def _tab(self, p: QPainter, text: str, x: float, y: float, align_center=False):
        p.setFont(T.font("mono", 11, "semibold"))
        fm = p.fontMetrics()
        w, h = fm.horizontalAdvance(text) + 12, 18
        left = x - w / 2 if align_center else x
        left = min(max(2, left), self.width() - w - 2)
        y = min(max(2, y), self.height() - h - 2)
        base = y
        for k in (0, 1, -1, 2, -2, 3, -3):       # nearest free slot, down first then up
            cy = base + k * (h + 3)
            if cy < 2 or cy > self.height() - h - 2:
                continue
            if not any(QRectF(left, cy, w, h).adjusted(-2, -2, 2, 2).intersects(o) for o in self._placed):
                y = cy
                break
        self._placed.append(QRectF(left, y, w, h))
        p.fillRect(QRectF(left, y, w, h), T.qc(T.OFFWHITE))
        p.setPen(T.qc(T.INK))
        p.drawText(QRectF(left, y, w, h), int(Qt.AlignCenter), text)

    def _poly(self, d: Detection, r: QRectF, xf: QTransform, pad: float) -> QPolygonF:
        rc = self._rect(d, r).adjusted(-pad, -pad, pad, pad)
        return xf.map(QPolygonF([rc.topLeft(), rc.topRight(), rc.bottomRight(), rc.bottomLeft()]))

    def _draw_overlay(self, p: QPainter, r: QRectF, real: bool):
        sc = self.scene
        xf = QTransform() if real else self._xf(r)
        dets = ([sc.main_box] if sc.main_box else []) + list(sc.objects)
        for d in dets:
            poly = self._poly(d, r, xf, 4)
            pen = QPen(T.qc(T.OFFWHITE), 2)
            if d.dashed:
                pen.setStyle(Qt.DashLine)
                pen.setWidthF(1.6)
            p.setPen(pen)
            p.setBrush(Qt.NoBrush)
            p.drawPolygon(poly)
            b = poly.boundingRect()
            conf = "" if d.conf is None else f" {d.conf:.2f}"
            txt = f"{d.name}{conf}"
            if d.dashed:                       # reference region: label sits under its lower-left corner
                self._tab(p, txt, b.left(), b.bottom() + 3)
            elif d.label_below:
                self._tab(p, txt, b.center().x(), b.bottom() + 3, True)
            else:
                self._tab(p, txt, b.center().x(), b.top() - 21, True)
        # rack axes
        ox, oy = sc.rack_origin
        o = xf.map(QPointF(ox * r.width(), oy * r.height()))
        ln = sc.rack_len * r.width()
        ex = xf.map(QPointF(ox * r.width() + ln, oy * r.height()))
        ey = xf.map(QPointF(ox * r.width(), oy * r.height() + ln))
        p.setPen(QPen(T.qc(T.OFFWHITE), 2))
        p.drawLine(o, ex)
        self._arrow(p, o, ex)
        dp = QPen(T.qc(T.OFFWHITE), 1.6, Qt.DashLine)
        p.setPen(dp)
        p.drawLine(o, ey)
        self._arrow(p, o, ey)
        self._tab(p, "+X", ex.x() + 4, ex.y() - 9)
        self._tab(p, "+Y", ey.x() + 4, ey.y() - 9)
        # hands
        for h in sc.hands:
            tip = xf.map(QPointF(h.tip[0] * r.width(), h.tip[1] * r.height()))
            wr = xf.map(QPointF(h.wrist[0] * r.width(), h.wrist[1] * r.height()))
            p.setPen(QPen(T.qc(T.OFFWHITE), 1.5))
            p.drawLine(wr, tip)
            p.setBrush(T.qc(T.OFFWHITE))
            p.setPen(QPen(T.qc(T.INK), 1.5))
            p.drawEllipse(tip, 5.5, 5.5)
            p.drawEllipse(wr, 4.5, 4.5)
            self._tab(p, f"hand {h.conf:.2f}", wr.x() - 20, wr.y() + 10)

    @staticmethod
    def _arrow(p: QPainter, a: QPointF, b: QPointF):
        ang = math.atan2(b.y() - a.y(), b.x() - a.x())
        pts = [b, QPointF(b.x() - 9 * math.cos(ang - 0.4), b.y() - 9 * math.sin(ang - 0.4)),
               QPointF(b.x() - 9 * math.cos(ang + 0.4), b.y() - 9 * math.sin(ang + 0.4))]
        p.save()
        p.setPen(Qt.NoPen)
        p.setBrush(T.qc(T.OFFWHITE))
        p.drawPolygon(QPolygonF(pts))
        p.restore()

    # finish + HUD --------------------------------------------------------------------
    def _draw_finish(self, p: QPainter, r: QRectF):
        vg = QRadialGradient(r.center(), r.width() * 0.62)
        vg.setColorAt(0.55, QColor(0, 0, 0, 0))
        vg.setColorAt(1.0, QColor(0, 0, 0, 90))
        p.fillRect(r, vg)
        if self.frame is None:
            p.drawTiledPixmap(r.toRect(), self._noise)
        p.setPen(QPen(T.qc(T.OFFWHITE, 170), 2))
        m, L = 12.0, 18.0
        for sx, x in ((1, r.left() + m), (-1, r.right() - m)):
            for sy, y in ((1, r.top() + m), (-1, r.bottom() - m)):
                p.drawLine(QPointF(x, y), QPointF(x + sx * L, y))
                p.drawLine(QPointF(x, y), QPointF(x, y + sy * L))

    def _hud(self, p: QPainter, text: str, x: float, y: float, right=False):
        p.setFont(T.font("mono", 11, "semibold", 0.4))
        w = p.fontMetrics().horizontalAdvance(text) + 14
        left = x - w if right else x
        p.fillRect(QRectF(left, y, w, 20), QColor(10, 12, 14, 150))
        p.setPen(T.qc(T.OFFWHITE))
        p.drawText(QRectF(left, y, w, 20), int(Qt.AlignCenter), text)
        return w

    def _draw_hud(self, p: QPainter, r: QRectF):
        x0, y0 = r.left() + 34, r.top() + 22
        self._hud(p, f"{self.cam_label} · T+{self.stamp}", x0, y0)
        w = self._hud(p, "Camera up not used", r.right() - 34, y0, right=True)
        # up-arrow glyph left of the label
        ax = r.right() - 34 - w - 14
        p.setPen(QPen(T.qc(T.OFFWHITE), 1.6))
        p.drawLine(QPointF(ax, y0 + 16), QPointF(ax, y0 + 4))
        p.drawLine(QPointF(ax, y0 + 4), QPointF(ax - 4, y0 + 9))
        p.drawLine(QPointF(ax, y0 + 4), QPointF(ax + 4, y0 + 9))
        yb = r.bottom() - 42
        if self.frame is None:
            self._hud(p, f"Setup rotation {self.scene.rotation % 360}°", x0, yb)
        self._hud(p, f"{self.n_objects} objects · {self.n_hands} hand{'s' if self.n_hands != 1 else ''}",
                  r.right() - 34, yb, right=True)
