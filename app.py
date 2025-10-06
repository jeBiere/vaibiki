import os
import sys
import sounddevice as sd
from PyQt5.QtCore import QTimer, Qt
from PyQt5.QtWidgets import QWidget
from PyQt5.QtGui import QPainter

from audio_processor import AudioProcessor
from components.visualization import Visualization
from components.clock import ClockWidget
from components.overlay import Overlay

# Для систем без Wayland
os.environ["QT_QPA_PLATFORM"] = "xcb"


class AudioVisualizer(QWidget):
    def __init__(self, config):
        super().__init__()
        self.config = config
        self._init_window()
        self._init_components()
        self._start_audio_stream()
        self._start_timer()

    def _init_window(self):
        self.setWindowTitle("Visualizer")
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnBottomHint)
        self.setAttribute(Qt.WA_TranslucentBackground)

        if sys.platform == "linux":
            try:
                self.setAttribute(Qt.WA_X11NetWmWindowTypeDesktop)
            except Exception:
                pass

        vis_conf = self.config["visualizer"]
        self.setGeometry(
            vis_conf["x"],
            vis_conf["y"],
            vis_conf["width"],
            vis_conf["height"]
        )

    def _init_components(self):
        self.audio_processor = AudioProcessor()
        self.visualization = Visualization(self.config)
        self.clock = ClockWidget(self.config)
        self.overlay = Overlay(self.config, self.size())

    def _start_audio_stream(self):
        self.stream = sd.InputStream(
            callback=self.audio_processor.audio_callback,
            channels=1,
            samplerate=self.config.get("samplerate", 44100),
            blocksize=self.config.get("blocksize", 1024)
        )
        self.stream.start()

    def _start_timer(self):
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update)
        self.timer.start(30)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        fft_data = self.audio_processor.get_fft_data()
        self.visualization.fft_data = fft_data  # лучше: self.visualization.set_fft_data(fft_data)

        self.visualization.paint(painter, self.size())
        self.clock.paint(painter, self.size())
        self.overlay.paint(painter, self.size())
