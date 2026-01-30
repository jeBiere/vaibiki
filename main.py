import sys
import argparse
from pathlib import Path
from PyQt5.QtWidgets import QApplication
from app import AudioVisualizer
from configurator import run_configurator
from config import load_config
from overlay_manager import OverlayManager
from platform import select_backend, apply_platform_env

CONFIG_PATH = Path("config.yaml")


def apply_linux_window_hack():
    if sys.platform == "linux":
        try:
            import subprocess
            subprocess.run(["wmctrl", "-r", "Visualizer", "-b", "add,below"])
        except Exception:
            pass


def main():
    parser = argparse.ArgumentParser(description="Запуск аудиовизуализатора с опциональным оверлеем.")
    parser.add_argument("--overlay", type=str, help="Путь к изображению оверлея")
    parser.add_argument("--configurator", action="store_true", help="Запуск окна конфигуратора")
    parser.add_argument("--backend", type=str, choices=["auto", "x11", "wayland"], help="Backend: auto|x11|wayland")
    parser.add_argument("--wayland-layer", type=str, choices=["background", "bottom", "top", "overlay"], help="Layer shell режим")
    args = parser.parse_args()

    if args.configurator:
        run_configurator(CONFIG_PATH)
        return

    if args.overlay:
        OverlayManager(CONFIG_PATH).process(args.overlay)

    config = load_config(CONFIG_PATH)
    backend = select_backend(config, args.backend)
    apply_platform_env(backend, config, args.wayland_layer)

    app = QApplication(sys.argv)
    visualizer = AudioVisualizer(config, CONFIG_PATH, backend, args.wayland_layer)
    visualizer.showFullScreen()

    if backend == "x11":
        apply_linux_window_hack()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
