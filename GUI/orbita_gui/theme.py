"""Colours, fonts, global stylesheet. Fonts are bundled so the app never needs a network."""
from __future__ import annotations
from pathlib import Path
from PySide6.QtGui import QColor, QFont, QFontDatabase

PAPER = "#E6E8EA"       # window
SHEET = "#F4F5F6"       # panels
INK = "#14181C"
MUTED = "#59626A"
HAIR = "#C2C7CC"
ACCENT = "#1D4E89"      # the only non-semantic colour
NOMINAL = "#D3D7DB"
CAUTION = "#E39A00"
WARNING = "#D7301F"
CAUTION_TEXT = "#8A5A00"   # darker amber for small text on light paper
OFFWHITE = "#F2F2F0"


def qc(hex_: str, alpha: int = 255) -> QColor:
    c = QColor(hex_)
    c.setAlpha(alpha)
    return c


_FAMILIES = {"sans": "Overpass", "mono": "Overpass Mono"}
_STATUS = {"ok": False, "missing": []}


def load_fonts(fonts_dir: Path | None = None) -> dict:
    """Register bundled TTFs and verify the families really loaded. Falls back loudly."""
    fonts_dir = fonts_dir or Path(__file__).resolve().parent.parent / "assets" / "fonts"
    loaded: set[str] = set()
    for ttf in sorted(fonts_dir.glob("*.ttf")):
        fid = QFontDatabase.addApplicationFont(str(ttf))
        if fid >= 0:
            loaded.update(QFontDatabase.applicationFontFamilies(fid))
    missing = [f for f in _FAMILIES.values() if f not in loaded]
    if missing:
        _FAMILIES["sans"] = QFontDatabase.systemFont(QFontDatabase.GeneralFont).family()
        _FAMILIES["mono"] = QFontDatabase.systemFont(QFontDatabase.FixedFont).family()
        print(f"[orbita_gui] bundled font(s) missing: {missing}; using {_FAMILIES}")
    _STATUS.update(ok=not missing, missing=missing)
    return dict(_STATUS, families=dict(_FAMILIES))


_WEIGHT = {"regular": QFont.Weight.Normal, "semibold": QFont.Weight.DemiBold,
           "bold": QFont.Weight.Bold}


def font(kind: str, px: int, weight: str = "regular", spacing: float = 0.0) -> QFont:
    f = QFont(_FAMILIES[kind])
    f.setPixelSize(px)
    f.setWeight(_WEIGHT[weight])
    f.setHintingPreference(QFont.PreferFullHinting)
    if spacing:
        f.setLetterSpacing(QFont.AbsoluteSpacing, spacing)
    return f


STYLESHEET = f"""
QWidget {{ color: {INK}; }}
QMainWindow, QScrollArea, QScrollArea > QWidget > QWidget {{ background: {PAPER}; }}
QScrollArea {{ border: none; }}
QPushButton[seg="true"] {{
    background: {SHEET}; border: 1.5px solid {INK}; padding: 6px 14px; min-height: 18px;
}}
QPushButton[seg="true"]:hover {{ background: #DDE0E3; }}
QPushButton[seg="true"]:checked {{ background: {INK}; color: {SHEET}; }}
QPushButton[seg="true"]:focus {{ outline: none; }}
QScrollBar:vertical {{ background: {PAPER}; width: 12px; margin: 0; }}
QScrollBar::handle:vertical {{ background: #9AA2A9; min-height: 30px; }}
QScrollBar::add-line, QScrollBar::sub-line {{ height: 0; }}
"""
