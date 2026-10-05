"""PipelineBridge: thread-safe hand-off from a pipeline thread to the GUI thread.

    bridge = PipelineBridge()
    bridge.attach(console)             # in the GUI thread
    ...
    bridge.push_snapshot(snap)         # from ANY thread (a dict also works)
    bridge.push_frame(bgr_ndarray)     # from ANY thread; only the newest frame is kept
"""
from __future__ import annotations
import threading
from PySide6.QtCore import QObject, Signal, Slot, Qt
from PySide6.QtGui import QImage
from .state import Snapshot
from .adapters import snapshot_from_dict, bgr_to_qimage


class PipelineBridge(QObject):
    snapshot_ready = Signal(object)
    frame_ready = Signal()
    voice_toggled = Signal(bool)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._lock = threading.Lock()
        self._latest: QImage | None = None
        self._frame_pending = False
        self._console = None

    def attach(self, console):
        self._console = console
        self.snapshot_ready.connect(console.update_snapshot, Qt.QueuedConnection)
        self.frame_ready.connect(self._deliver_frame, Qt.QueuedConnection)
        console.voice_toggled.connect(self.voice_toggled)      # GUI -> pipeline (e.g. mute alerts)

    def push_snapshot(self, snap):
        if not isinstance(snap, Snapshot):
            snap = snapshot_from_dict(snap)
        self.snapshot_ready.emit(snap)

    def push_frame(self, bgr):
        img = bgr_to_qimage(bgr)
        with self._lock:
            self._latest = img
            if self._frame_pending:
                return                       # GUI hasn't drawn the last one yet: drop, keep newest
            self._frame_pending = True
        self.frame_ready.emit()

    @Slot()
    def _deliver_frame(self):
        with self._lock:
            img, self._latest, self._frame_pending = self._latest, None, False
        if self._console is not None and img is not None:
            self._console.set_frame(img)
