"""PipelineBridge: thread-safe hand-off from a pipeline thread to the GUI thread.

    bridge = PipelineBridge()
    bridge.attach(console)             # in the GUI thread
    ...
    bridge.push_update(bgr, snapshot)   # production: paired frame identity + state
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
    """One latest image/state slot and one queued Qt wakeup.

    snapshot_ready/frame_ready notify observers after main-thread delivery.
    Legacy separate pushes are for embedding/demo use; production pairs updates.
    """
    update_ready = Signal()
    snapshot_ready = Signal(object)
    frame_ready = Signal()
    voice_toggled = Signal(bool)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._lock = threading.Lock()
        self._latest: QImage | None = None
        self._snapshot: Snapshot | None = None
        self._pending = False
        self._console = None

    def attach(self, console):
        self._console = console
        self.update_ready.connect(self._deliver, Qt.QueuedConnection)
        console.voice_toggled.connect(self.voice_toggled)      # GUI -> pipeline (e.g. mute alerts)

    def push_snapshot(self, snap):
        if not isinstance(snap, Snapshot):
            snap = snapshot_from_dict(snap)
        self._store(snap=snap)

    def push_frame(self, bgr):
        self._store(img=bgr_to_qimage(bgr))

    def push_update(self, bgr, snap):
        """Production boundary: replace one complete frame/state pair atomically.

        At most one wakeup is queued. Intermediate display updates are dropped;
        inference and the authoritative event log keep every runtime decision.
        """
        if not isinstance(snap, Snapshot):
            snap = snapshot_from_dict(snap)
        self._store(img=bgr_to_qimage(bgr) if bgr is not None else None, snap=snap)

    def _store(self, *, img=None, snap=None):
        with self._lock:
            if img is not None:
                self._latest = img
            if snap is not None:
                self._snapshot = snap
            if self._pending:
                return
            self._pending = True
        self.update_ready.emit()

    @Slot()
    def _deliver(self):
        with self._lock:
            img, snap = self._latest, self._snapshot
            self._latest, self._snapshot, self._pending = None, None, False
        # This slot is entered by a queued connection on the Qt owner thread.
        # Both widget changes finish before Qt can paint the pair.
        if self._console is not None:
            if snap is not None:
                self._console.update_snapshot(snap)
            if img is not None:
                self._console.set_frame(img)
        if snap is not None:
            self.snapshot_ready.emit(snap)
        if img is not None:
            self.frame_ready.emit()
