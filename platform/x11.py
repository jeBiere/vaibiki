import os
import sys
from PyQt5.QtCore import Qt


def apply_env():
    os.environ.setdefault("QT_QPA_PLATFORM", "xcb")


def apply_window_flags(widget):
    widget.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnBottomHint)
    widget.setAttribute(Qt.WA_TranslucentBackground)
    if sys.platform == "linux":
        try:
            widget.setAttribute(Qt.WA_X11NetWmWindowTypeDesktop)
        except Exception:
            pass
