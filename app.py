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
        # В методе _init_components заменить создание AudioProcessor на:
        self.audio_processor = AudioProcessor(
            bar_count=self.config.get("bar_count", 100),
            samplerate=self.config.get("samplerate", 44100),
            blocksize=self.config.get("blocksize", 1024),
            buffer_blocks=self.config.get("buffer_blocks", 32),
            exp_smooth_factor=self.config.get("exp_smooth_factor", 0.4),
            max_change_speed=self.config.get("max_change_speed", 0.5),
            noise_floor=self.config.get("noise_floor", 0.02),
            peak_sharpness=self.config.get("peak_sharpness", 1.4),
            avg_window_size=self.config.get("avg_window_size", 5),
            visualization_mode=self.config.get("visualization_mode", "linear"),
            fmin=self.config.get("fmin", 100.0),
            fmax=self.config.get("fmax", 6000.0),
            cqt_bins_per_bar=self.config.get("cqt_bins_per_bar", 3),
            bins_per_octave=self.config.get("bins_per_octave", 12),
            accent_threshold=self.config.get("accent_threshold", 1.8),  # ДОБАВИТЬ
            accent_boost=self.config.get("accent_boost", 2.0)           # ДОБАВИТЬ
        )
                
        self.visualization = Visualization(self.config)
        self.clock = ClockWidget(self.config)
        
        # ДОБАВЛЕНО: возможность отключить оверлей
        if self.config.get("overlay_enabled", True):
            self.overlay = Overlay(self.config, self.size())
        else:
            self.overlay = None

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
        self.visualization.fft_data = fft_data

        self.visualization.paint(painter, self.size())
        self.clock.paint(painter, self.size())
        
        # ИСПРАВЛЕНО: рисуем оверлей только если он включён
        if self.overlay is not None:
            self.overlay.paint(painter, self.size())