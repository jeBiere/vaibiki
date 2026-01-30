import os
from PyQt5.QtCore import Qt


def apply_env(layer):
    os.environ.setdefault("QT_QPA_PLATFORM", "wayland")
    os.environ.setdefault("QT_WAYLAND_DISABLE_WINDOWDECORATION", "1")
    if layer in {"background", "bottom", "top", "overlay"}:
        os.environ.setdefault("QT_WAYLAND_SHELL_INTEGRATION", "layer-shell")


def apply_window_flags(widget, layer):
    flags = Qt.FramelessWindowHint
    if layer in {"overlay", "top"}:
        flags |= Qt.WindowStaysOnTopHint
    else:
        flags |= Qt.WindowStaysOnBottomHint
    widget.setWindowFlags(flags)
    widget.setAttribute(Qt.WA_TranslucentBackground)
