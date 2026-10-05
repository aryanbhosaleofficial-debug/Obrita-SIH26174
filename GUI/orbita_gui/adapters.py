"""Translate pipeline output into GUI Snapshots. This is the ONLY file that knows pipeline shapes.

Because the pipeline's real status object was not available when the GUI was written, the
mapping is a plain dict contract (documented in README.md). Fill the dict from your own
objects, or edit `snapshot_from_dict` to read your dataclass attributes directly.
"""
from __future__ import annotations
from typing import Any, Mapping
from PySide6.QtGui import QImage
from .state import (Snapshot, Step, Detection, Hand, Reading, ChainItem, LogEntry,
                    AlertEntry, NextStep, Scene)


def _g(d: Any, key: str, default=None):
    return d.get(key, default) if isinstance(d, Mapping) else getattr(d, key, default)


def _list(d, key, ctor):
    return [x if not isinstance(x, Mapping) else ctor(**x) for x in (_g(d, key, []) or [])]


def _det(x):
    return x if isinstance(x, Detection) else Detection(**x)


def snapshot_from_dict(d: Mapping[str, Any]) -> Snapshot:
    """Tolerant conversion: missing keys keep defaults, unknown keys are ignored."""
    sc = _g(d, "scene") or {}
    scene = Scene(
        simulated=_g(sc, "simulated", False),
        overlays_rendered=bool(_g(sc, "overlays_rendered", False)),
        rotation=int(_g(sc, "rotation", 0)),
        main_box=_det(_g(sc, "main_box")) if _g(sc, "main_box") else None,
        objects=[_det(o) for o in (_g(sc, "objects", []) or [])],
        hands=[h if isinstance(h, Hand) else Hand(**h) for h in (_g(sc, "hands", []) or [])],
    )
    ns = _g(d, "next_step")
    return Snapshot(
        status_level=_g(d, "status_level", "nominal"),
        status_text=_g(d, "status_text", ""),
        spoken=_g(d, "spoken", ""),
        met_seconds=float(_g(d, "met_seconds", 0.0)),
        stamp=_g(d, "stamp", "00:00:00.000"),
        confidence=_g(d, "confidence"),
        steps=_list(d, "steps", Step),
        next_step=ns if isinstance(ns, NextStep) else NextStep(**(ns or {})),
        readings=_list(d, "readings", Reading),
        chain=_list(d, "chain", ChainItem),
        alerts=_list(d, "alerts", AlertEntry),
        log=_list(d, "log", LogEntry),
        log_path=_g(d, "log_path", ""),
        scene=scene,
        recording=bool(_g(d, "recording", False)),
        lan_streaming=bool(_g(d, "lan_streaming", False)),
        local_only=bool(_g(d, "local_only", True)),
        voice_on=bool(_g(d, "voice_on", True)),
        footer=_g(d, "footer", ""),
    )


def bgr_to_qimage(arr) -> QImage:
    """OpenCV BGR (H,W,3) or gray (H,W) ndarray -> detached QImage (safe to hand across threads)."""
    h, w = arr.shape[:2]
    if arr.ndim == 2:
        img = QImage(arr.data, w, h, arr.strides[0], QImage.Format_Grayscale8)
    else:
        img = QImage(arr.data, w, h, arr.strides[0], QImage.Format_BGR888)
    return img.copy()
