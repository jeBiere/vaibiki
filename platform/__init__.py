import os

from . import x11
from . import wayland


def select_backend(config, cli_backend=None):
    backend = cli_backend or config.get("platform", {}).get("backend", "auto")
    if backend == "auto":
        if os.environ.get("WAYLAND_DISPLAY") or os.environ.get("XDG_SESSION_TYPE") == "wayland":
            return "wayland"
        return "x11"
    if backend == "wayland" and not (
        os.environ.get("WAYLAND_DISPLAY") or os.environ.get("XDG_SESSION_TYPE") == "wayland"
    ):
        return "x11"
    return backend


def apply_platform_env(backend, config, cli_wayland_layer=None):
    if backend == "wayland":
        layer = cli_wayland_layer or config.get("platform", {}).get("wayland_layer", "background")
        wayland.apply_env(layer)
    else:
        x11.apply_env()


def apply_window_flags(widget, backend, config, cli_wayland_layer=None):
    if backend == "wayland":
        layer = cli_wayland_layer or config.get("platform", {}).get("wayland_layer", "background")
        wayland.apply_window_flags(widget, layer)
    else:
        x11.apply_window_flags(widget)
