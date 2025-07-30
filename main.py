import sys
import argparse
from pathlib import Path
from PyQt5.QtWidgets import QApplication
from app import AudioVisualizer
from config import load_config
from overlay_manager import OverlayManager

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
    args = parser.parse_args()

    if args.overlay:
        OverlayManager(CONFIG_PATH).process(args.overlay)

    config = load_config(CONFIG_PATH)

    app = QApplication(sys.argv)
    visualizer = AudioVisualizer(config)
    visualizer.showFullScreen()

    apply_linux_window_hack()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
