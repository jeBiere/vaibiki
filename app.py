import sounddevice as sd
from PyQt5.QtCore import QTimer, Qt, QFileSystemWatcher
from PyQt5.QtWidgets import QWidget
from PyQt5.QtGui import QPainter

from audio import create_audio_processor
from components.visualization import Visualization
from components.clock import ClockWidget
from components.overlay import Overlay
from config import load_config
from platform import apply_window_flags


class AudioVisualizer(QWidget):
    def __init__(self, config, config_path=None, backend="x11", wayland_layer=None):
        super().__init__()
        self.config_path = config_path
        self.config = config
        self.backend = backend
        self.wayland_layer = wayland_layer
        self._init_window()
        self._init_components()
        self._start_audio_stream()
        self._start_timer()
        self._init_config_watcher()

    def _init_window(self):
        self.setWindowTitle("Visualizer")
        apply_window_flags(self, self.backend, self.config, self.wayland_layer)

        vis_conf = self.config["visualizer"]
        self.setGeometry(
            vis_conf["x"],
            vis_conf["y"],
            vis_conf["width"],
            vis_conf["height"]
        )

    def _init_components(self):
        self.audio_processor = create_audio_processor(self.config)
                
        self.visualization = Visualization(self.config)
        self.clock = ClockWidget(self.config)
        
        if self.config.get("overlay", {}).get("enabled", True):
            self.overlay = Overlay(self.config, self.size())
        else:
            self.overlay = None

    def _start_audio_stream(self):
        audio_conf = self.config["audio"]
        self.stream = sd.InputStream(
            callback=self.audio_processor.audio_callback,
            channels=1,
            samplerate=audio_conf.get("samplerate", 44100),
            blocksize=audio_conf.get("blocksize", 1024)
        )
        self.stream.start()

    def _start_timer(self):
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update)
        self.timer.start(30)

    def _init_config_watcher(self):
        if not self.config_path:
            return
        self._reload_timer = QTimer(self)
        self._reload_timer.setSingleShot(True)
        self._reload_timer.timeout.connect(self._reload_config)

        self._watcher = QFileSystemWatcher(self)
        self._watcher.addPath(str(self.config_path))
        self._watcher.fileChanged.connect(self._schedule_reload)

    def _schedule_reload(self):
        self._reload_timer.start(200)

    def _reload_config(self):
        self.config = load_config(self.config_path)
        self._apply_config()
        if self.config_path and str(self.config_path) not in self._watcher.files():
            self._watcher.addPath(str(self.config_path))

    def _apply_config(self):
        vis_conf = self.config["visualizer"]
        self.setGeometry(
            vis_conf["x"],
            vis_conf["y"],
            vis_conf["width"],
            vis_conf["height"]
        )
        apply_window_flags(self, self.backend, self.config, self.wayland_layer)
        self.visualization = Visualization(self.config)
        self.clock = ClockWidget(self.config)
        if self.config.get("overlay", {}).get("enabled", True):
            self.overlay = Overlay(self.config, self.size())
        else:
            self.overlay = None

        try:
            self.stream.stop()
            self.stream.close()
        except Exception:
            pass
        self.audio_processor = create_audio_processor(self.config)
        self._start_audio_stream()
        self.update()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if self.overlay is not None:
            self.overlay = Overlay(self.config, self.size())

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        fft_data = self.audio_processor.get_fft_data()
        self.visualization.fft_data = fft_data

        self.visualization.paint(painter, self.size())
        self.clock.paint(painter, self.size())
        
        if self.overlay is not None:
            self.overlay.paint(painter, self.size())
