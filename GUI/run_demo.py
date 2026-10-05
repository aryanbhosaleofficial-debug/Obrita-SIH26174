"""Standalone ORBITA GUI with built-in sample data. No pipeline modules, no network.

    pip install -r requirements.txt
    python run_demo.py
    python run_demo.py --shot out.png --trial wrong --rotation 90   # render one screenshot and exit
"""
import argparse, sys
from orbita_gui.main_window import OrbitaWindow, make_app
from orbita_gui.mock import MockProvider


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--trial", default="correct", choices=["correct", "skipped", "wrong"])
    ap.add_argument("--rotation", type=int, default=0, choices=[0, 90, 180, 270])
    ap.add_argument("--shot", help="save a PNG of the window and exit (works with QT_QPA_PLATFORM=offscreen)")
    ap.add_argument("--size", default="1360x900")
    a = ap.parse_args()
    app = make_app(sys.argv)
    win = OrbitaWindow(show_demo_controls=True)
    mock = MockProvider()
    mock.snapshot.connect(win.console.update_snapshot)
    win.console.trial_requested.connect(lambda k: (mock.set_trial(k), win.console.set_demo_state(k, mock.rotation)))
    win.console.rotation_requested.connect(mock.set_rotation)
    win.console.voice_toggled.connect(mock.set_voice)
    mock.trial, mock.rotation = a.trial, a.rotation
    win.console.set_demo_state(a.trial, a.rotation)
    w, h = (int(x) for x in a.size.split("x"))
    win.resize(w, h)
    win.show()
    mock.start()
    if a.shot:
        mock.stop()
        mock.emit_now()
        app.processEvents()
        win.grab().save(a.shot)
        print("saved", a.shot)
        return 0
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
