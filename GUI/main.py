import sys
from PySide6.QtWidgets import QApplication
from gui.main_window import MainWindow
from gui.theme import load_fonts
import os

def main():
    os.environ["QT_AUTO_SCREEN_SCALE_FACTOR"] = "1"
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    load_fonts()
    window = MainWindow()
    window.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
