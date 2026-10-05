"""Existing Qt console + bridge, with inference exclusively in a worker thread."""
from queue import Queue
import signal
import sys
from threading import Event, Thread


def run_gui(build_runtime, args):
    # GUI is optional; headless runtime never imports Qt.
    from PySide6.QtCore import Qt, QTimer, QObject, Signal
    from PySide6.QtGui import QShortcut, QKeySequence
    from GUI.orbita_gui.main_window import make_app, OrbitaWindow
    from GUI.orbita_gui.bridge import PipelineBridge

    app = make_app([sys.argv[0]])
    window = OrbitaWindow(show_demo_controls=False)
    bridge = PipelineBridge()
    bridge.attach(window.console)
    stop, controls = Event(), Queue()
    bridge.voice_toggled.connect(lambda enabled: controls.put(("voice", enabled)))
    window.closed.connect(stop.set)
    window.closed.connect(app.quit)
    shortcuts = []
    for key, command in (("Space", "pause"), ("C", "resume"), ("R", "reset"), ("A", "abort")):
        shortcut = QShortcut(QKeySequence(key), window)
        shortcut.activated.connect(lambda cmd=command: controls.put((cmd, None)))
        shortcuts.append(shortcut)
    for key in ("Q", "Escape"):
        shortcut = QShortcut(QKeySequence(key), window)
        shortcut.activated.connect(window.close)
        shortcuts.append(shortcut)

    class Signals(QObject):
        finished = Signal(object)
    signals = Signals()
    result = []
    def finished(summary):
        # EOF/fatal error exits predictably after queued bridge delivery.
        def finish_window():
            try:
                if args.gui_shot:
                    args.gui_shot.parent.mkdir(parents=True, exist_ok=True)
                    if not window.grab().save(str(args.gui_shot)):
                        raise OSError(f"GUI screenshot could not be saved: {args.gui_shot}")
            except OSError as exc:
                summary["error"] = str(exc)
                summary["exit_reason"] = "error"
            finally:
                window.close()
        QTimer.singleShot(150, finish_window)
    signals.finished.connect(finished, Qt.QueuedConnection)

    def worker():
        try:
            runtime, frames, resources = build_runtime(args, gui=bridge, stop=stop, controls=controls)
            with resources:
                summary = runtime.run(frames, max_frames=args.max_frames)
        except Exception as exc:
            summary = {"error": f"{type(exc).__name__}: {exc}", "exit_reason": "error", "frames": 0}
            bridge.push_snapshot({"status_level": "warning", "status_text": summary["error"],
                "voice_on": False, "alerts": [{"t": "", "level": "warning", "text": summary["error"]}],
                "system_health": {"Runtime": "ERROR"}})
        result.append(summary)  # retain summary even if GUI closes before signal delivery
        signals.finished.emit(summary)
    thread = Thread(target=worker, name="full-system-inference", daemon=False)
    timer = QTimer()
    timer.timeout.connect(lambda: None)  # let Python handle Ctrl+C while Qt runs
    timer.start(100)
    previous = signal.getsignal(signal.SIGINT)
    signal.signal(signal.SIGINT, lambda *_: window.close())
    try:
        window.show()
        QTimer.singleShot(0, thread.start)
        app.exec()
    finally:
        stop.set()
        if thread.ident is not None:
            thread.join(timeout=10.)
        signal.signal(signal.SIGINT, previous)
        timer.stop()
    if thread.is_alive():
        raise RuntimeError("capture/inference worker failed to stop within 10 seconds")
    return result[-1] if result else {"error": None, "exit_reason": "gui_closed", "frames": 0}
