"""Embed the console in your own app and feed it from a worker thread.

Replace `fake_pipeline` with your real loop. The only GUI calls it makes are
bridge.push_snapshot(...) and bridge.push_frame(...), both safe from any thread.
"""
import os, sys, time, threading
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import numpy as np
from orbita_gui.main_window import make_app
from orbita_gui import ConsoleWidget, PipelineBridge
from orbita_gui.mock import build_snapshot
from PySide6.QtWidgets import QMainWindow


def fake_pipeline(bridge: PipelineBridge, stop: threading.Event):
    t0 = time.monotonic()
    while not stop.is_set():
        frame = np.full((480, 640, 3), 40, np.uint8)            # stand-in for cv2 frame (BGR)
        frame[:, :, 2] = int(80 + 60 * np.sin(time.monotonic()))
        bridge.push_frame(frame)
        snap = build_snapshot("correct", 0, time.monotonic() - t0)
        snap.scene.simulated = False                            # real video: don't draw the demo scene
        bridge.push_snapshot(snap)
        time.sleep(1 / 15)


if __name__ == "__main__":
    app = make_app(sys.argv)
    console = ConsoleWidget(show_demo_controls=False)           # hide demo-only trial/rotation buttons
    win = QMainWindow(); win.setCentralWidget(console); win.resize(1360, 900); win.show()
    bridge = PipelineBridge(); bridge.attach(console)
    bridge.voice_toggled.connect(lambda on: print("voice enabled:", on))   # GUI -> pipeline
    stop = threading.Event()
    threading.Thread(target=fake_pipeline, args=(bridge, stop), daemon=True).start()
    app.aboutToQuit.connect(stop.set)
    sys.exit(app.exec())
