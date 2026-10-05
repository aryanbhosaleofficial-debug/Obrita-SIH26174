"""ORBITA GUI: offline PySide6 console for the SIH26174 BAS experiment monitor.

Two ways to use it:
  * standalone demo:   python run_demo.py            (built-in sample data)
  * embedded module:   from orbita_gui import ConsoleWidget, PipelineBridge, Snapshot
"""
from .state import (Snapshot, Step, Detection, Hand, Reading, ChainItem,
                    LogEntry, AlertEntry, NextStep)
from .console import ConsoleWidget
from .main_window import OrbitaWindow
from .bridge import PipelineBridge
from .adapters import snapshot_from_dict, bgr_to_qimage

__all__ = ["Snapshot", "Step", "Detection", "Hand", "Reading", "ChainItem",
           "LogEntry", "AlertEntry", "NextStep", "ConsoleWidget", "OrbitaWindow",
           "PipelineBridge", "MockProvider", "snapshot_from_dict", "bgr_to_qimage"]
__version__ = "1.0.0"


def __getattr__(name):
    # Keep the public demo import compatible without loading mock code in production.
    if name == "MockProvider":
        from .mock import MockProvider
        return MockProvider
    raise AttributeError(name)
