from __future__ import annotations
from PySide6.QtCore import Signal
from PySide6.QtWidgets import QMainWindow, QApplication
from PySide6.QtGui import QIcon
from . import theme as T
from .console import ConsoleWidget


class OrbitaWindow(QMainWindow):
    closed = Signal()

    def __init__(self, show_demo_controls: bool = True):
        super().__init__()
        self.setWindowTitle("ORBITA · BAS experiment monitor · SIH26174")
        self.console = ConsoleWidget(show_demo_controls)
        self.setCentralWidget(self.console)
        self.setMinimumSize(1240, 720)
        self.resize(1360, 900)

    def closeEvent(self, e):
        self.closed.emit()
        super().closeEvent(e)


def make_app(argv=None) -> QApplication:
    """Create the QApplication, load bundled fonts, apply the stylesheet."""
    app = QApplication.instance() or QApplication(argv or [])
    info = T.load_fonts()
    app.setFont(T.font("sans", 14))
    app.setStyleSheet(T.STYLESHEET)
    app.setProperty("orbita_fonts_ok", info["ok"])
    return app
