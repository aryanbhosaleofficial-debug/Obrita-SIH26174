"""Offscreen checks: every trial x rotation renders, widgets never overlap, fonts really loaded.
Run:  QT_QPA_PLATFORM=offscreen python -m pytest -q   (or python tests/test_smoke.py)
"""
import os, sys, threading
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import numpy as np
from PySide6.QtWidgets import QWidget
from orbita_gui.main_window import OrbitaWindow, make_app
from orbita_gui.mock import build_snapshot, TRIALS
from orbita_gui.bridge import PipelineBridge
from orbita_gui.adapters import snapshot_from_dict

app = make_app([])


def _window(w=1360, h=900):
    win = OrbitaWindow()
    win.resize(w, h)
    win.show()
    return win


def test_fonts_loaded():
    assert app.property("orbita_fonts_ok") is True


def test_all_trials_and_rotations():
    win = _window()
    for t in TRIALS:
        for r in (0, 90, 180, 270):
            win.console.update_snapshot(build_snapshot(t, r))
            app.processEvents()
            cam = win.console.camera
            assert abs(cam.height() - cam.width() * 9 / 16) <= 1
            assert not win.grab().isNull()


def test_camera_not_overlapped_by_controls():
    win = _window()
    win.console.update_snapshot(build_snapshot("correct", 0))
    app.processEvents()
    c = win.console
    cam_bottom = c.camera.mapTo(win, c.camera.rect().bottomLeft()).y()
    ctl_top = c.demo_row.mapTo(win, c.demo_row.rect().topLeft()).y()
    assert ctl_top > cam_bottom


def test_footer_below_columns():
    win = _window()
    win.console.update_snapshot(build_snapshot("skipped", 90))
    app.processEvents()
    c = win.console
    body = c.footer.parentWidget()
    log_bottom = c.log.mapTo(body, c.log.rect().bottomLeft()).y()
    assert c.footer.mapTo(body, c.footer.rect().topLeft()).y() > log_bottom
    chain_bottom = c.chain.mapTo(body, c.chain.rect().bottomLeft()).y()
    assert c.footer.mapTo(body, c.footer.rect().topLeft()).y() > chain_bottom


def test_bridge_thread_safe():
    win = _window()
    br = PipelineBridge()
    br.attach(win.console)
    snap = build_snapshot("wrong", 0)

    def work():
        br.push_snapshot(snap)
        for _ in range(20):
            br.push_frame(np.zeros((48, 64, 3), np.uint8))
        br.push_snapshot(snapshot_from_dict({"status_text": "from dict", "steps": [{"id": "a", "text": "A"}]}))
    th = threading.Thread(target=work)
    th.start(); th.join()
    for _ in range(5):
        app.processEvents()
    assert win.console.status.msg.text() == "from dict"
    assert win.console.camera.frame is not None


if __name__ == "__main__":
    for n, f in list(globals().items()):
        if n.startswith("test_"):
            f(); print("ok", n)
