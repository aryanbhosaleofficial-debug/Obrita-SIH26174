import sys
import os
import pytest
from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QPixmap

# Ensure GUI is in path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from gui.main_window import MainWindow
from gui.theme import load_fonts

def test_smoke():
    # Use offscreen platform for testing
    os.environ["QT_QPA_PLATFORM"] = "offscreen"
    
    app = QApplication.instance()
    if not app:
        app = QApplication(sys.argv)
        
    load_fonts()
    window = MainWindow()
    window.resize(1440, 900)
    window.show()
    
    trials = ["Correct run", "Skipped step", "Wrong order"]
    rots = [0, 90, 180, 270]
    
    for t in trials:
        for r in rots:
            window.provider.set_trial(t)
            window.provider.set_rotation(r)
            # Process events so the window updates
            app.processEvents()
            
            # Take a screenshot
            pixmap = window.grab()
            name = t.replace(" ", "_").lower()
            pixmap.save(f"screenshot_{name}_{r}.png")
            
    assert True, "Smoke test completed without crashes"
