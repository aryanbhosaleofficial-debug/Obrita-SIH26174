from PySide6.QtGui import QColor, QFont, QFontDatabase
import os

# Colors
PAPER = QColor("#EDEEF0")
INK = QColor("#11151A")
INK_2 = QColor("#424A54")
INK_3 = QColor("#59616C")
RULE_HEAVY = QColor("#11151A")  # 2px ink
RULE_MID = QColor("#B9BEC4")
RULE_LIGHT = QColor("#D0D4D9")
BAR_TRACK = QColor("#CDD1D6")
BLUE = QColor("#0B3D91")
AMBER = QColor("#E39A00")
AMBER_TEXT = QColor("#8F5B00")
RED = QColor("#D7301F")
RED_TEXT = QColor("#B3261E")

ROW_ACTIVE = QColor("#FFFFFF")
ROW_SKIPPED = QColor("#FBEBC2")
ROW_WRONG = QColor("#F8D7D2")

NOMINAL_STATUS_BAR = QColor("#D3D7DB")

# Typography
FONT_FAMILY_SANS = "Overpass"
FONT_FAMILY_MONO = "Overpass Mono"

def load_fonts():
    font_dir = os.path.join(os.path.dirname(__file__), "..", "assets", "fonts")
    if os.path.exists(font_dir):
        for font_file in os.listdir(font_dir):
            if font_file.endswith(".ttf") or font_file.endswith(".otf"):
                QFontDatabase.addApplicationFont(os.path.join(font_dir, font_file))
    
    # Check if loaded, otherwise we use fallbacks
    families = QFontDatabase.families()
    global FONT_FAMILY_SANS, FONT_FAMILY_MONO
    if "Overpass" not in families:
        FONT_FAMILY_SANS = "Helvetica Neue, Arial, sans-serif"
    if "Overpass Mono" not in families:
        FONT_FAMILY_MONO = "Consolas, monospace"

def get_font(size=14, weight=QFont.Weight.Normal, mono=False):
    family = FONT_FAMILY_MONO if mono else FONT_FAMILY_SANS
    if "," in family: # Fallback list handling (simplified for Qt)
        family = family.split(",")[0].strip()
    font = QFont(family, size, weight)
    if mono:
        font.setStyleHint(QFont.StyleHint.Monospace)
    return font

def meta_font():
    return get_font(12, QFont.Weight.Normal, mono=False)

def body_font():
    return get_font(14, QFont.Weight.Normal, mono=False)

def key_text_font():
    return get_font(18, QFont.Weight.Normal, mono=False)

def clock_font():
    return get_font(22, QFont.Weight.Normal, mono=True)

def section_title_font():
    return get_font(14, QFont.Weight.Bold, mono=False)

def mono_font(size=12, weight=QFont.Weight.Normal):
    return get_font(size, weight, mono=True)
