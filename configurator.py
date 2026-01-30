import math
import sys
from pathlib import Path

import sounddevice as sd
from PyQt5.QtCore import QTimer, Qt, QSize
from PyQt5.QtGui import QColor, QFont
from PyQt5.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QColorDialog,
    QFileDialog,
    QFontComboBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QMainWindow,
    QPushButton,
    QSpinBox,
    QDoubleSpinBox,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from audio import create_audio_processor
from components.preview_canvas import PreviewCanvas
from config import load_config, save_config
from overlay_manager import OverlayManager


def _get_path(config, path, default=None):
    cur = config
    for key in path.split("."):
        if not isinstance(cur, dict) or key not in cur:
            return default
        cur = cur[key]
    return cur


def _set_path(config, path, value):
    cur = config
    parts = path.split(".")
    for key in parts[:-1]:
        cur = cur.setdefault(key, {})
    cur[parts[-1]] = value


class ConfiguratorWindow(QMainWindow):
    def __init__(self, config_path: Path):
        super().__init__()
        self.config_path = config_path
        self.config = load_config(self.config_path)
        self._saving = False
        self._preview_phase = 0.0
        self._audio_stream = None
        self._audio_processor = None
        self._init_ui()
        self._init_preview_timer()

    def _init_ui(self):
        self.setWindowTitle("Configurator")
        self.resize(1400, 800)

        root = QWidget()
        self.setCentralWidget(root)
        layout = QVBoxLayout(root)

        main_row = QHBoxLayout()
        layout.addLayout(main_row)

        self.sidebar = QListWidget()
        self.sidebar.addItems(["Visualizer", "Clock", "Overlay", "Audio", "Window/System", "Presets"])
        self.sidebar.setMaximumWidth(220)
        self.sidebar.currentRowChanged.connect(self._on_section_changed)

        self.props_stack = QStackedWidget()
        self.props_stack.addWidget(self._build_visualizer_panel())
        self.props_stack.addWidget(self._build_clock_panel())
        self.props_stack.addWidget(self._build_overlay_panel())
        self.props_stack.addWidget(self._build_audio_panel())
        self.props_stack.addWidget(self._build_system_panel())
        self.props_stack.addWidget(self._build_presets_panel())

        screen = QApplication.primaryScreen()
        screen_size = screen.availableGeometry().size() if screen else None
        screen_size = screen_size if screen_size else QSize(1920, 1080)
        self.preview = PreviewCanvas(self.config, screen_size)
        self.preview.setStyleSheet("background: #0f0f0f;")
        self.preview.visualizer_rect_changed.connect(self._on_preview_rect_changed)

        main_row.addWidget(self.sidebar)
        main_row.addWidget(self.preview, 1)
        main_row.addWidget(self.props_stack)

        footer = QHBoxLayout()
        layout.addLayout(footer)

        self.status = QLabel("Config loaded.")
        save_btn = QPushButton("Save")
        reload_btn = QPushButton("Reload")

        save_btn.clicked.connect(self._save_config)
        reload_btn.clicked.connect(self._reload_config)

        footer.addWidget(self.status, 1)
        footer.addWidget(reload_btn)
        footer.addWidget(save_btn)

        self.sidebar.setCurrentRow(0)

    def _init_preview_timer(self):
        self.preview_timer = QTimer(self)
        self.preview_timer.timeout.connect(self._tick_preview)
        self.preview_timer.start(30)

        self.save_timer = QTimer(self)
        self.save_timer.setSingleShot(True)
        self.save_timer.timeout.connect(self._save_config)

    def _schedule_save(self):
        if not self._saving:
            self.save_timer.start(500)

    def _tick_preview(self):
        mode = _get_path(self.config, "preview.mode", "fake")
        bars = _get_path(self.config, "audio.bar_count", 64)
        if mode == "live":
            if self._audio_processor is None:
                self._start_live_preview()
            data = self._audio_processor.get_fft_data() if self._audio_processor else [0] * bars
            self.preview.set_fft_data(data)
        else:
            self._stop_live_preview()
            self._preview_phase += 0.08
            data = []
            for i in range(bars):
                val = 0.5 + 0.5 * math.sin(self._preview_phase + i * 0.2)
                data.append(max(0.0, min(1.0, val)))
            self.preview.set_fft_data(data)
        self.preview.update()

    def _start_live_preview(self):
        try:
            self._audio_processor = create_audio_processor(self.config)
            audio_conf = self.config["audio"]
            self._audio_stream = sd.InputStream(
                callback=self._audio_processor.audio_callback,
                channels=1,
                samplerate=audio_conf.get("samplerate", 44100),
                blocksize=audio_conf.get("blocksize", 1024),
            )
            self._audio_stream.start()
        except Exception:
            self._audio_processor = None
            self._audio_stream = None
            _set_path(self.config, "preview.mode", "fake")

    def _stop_live_preview(self):
        if self._audio_stream:
            try:
                self._audio_stream.stop()
                self._audio_stream.close()
            except Exception:
                pass
        self._audio_stream = None
        self._audio_processor = None

    def _on_section_changed(self, idx):
        self.props_stack.setCurrentIndex(idx)

    def _build_visualizer_panel(self):
        panel = QWidget()
        layout = QVBoxLayout(panel)

        form = QFormLayout()
        self.vis_x = QSpinBox()
        self.vis_y = QSpinBox()
        self.vis_w = QSpinBox()
        self.vis_h = QSpinBox()
        self.vis_shift = QSpinBox()
        for box in (self.vis_x, self.vis_y, self.vis_w, self.vis_h):
            box.setRange(0, 10000)
        self.vis_shift.setRange(0, 2000)
        form.addRow("X", self.vis_x)
        form.addRow("Y", self.vis_y)
        form.addRow("Width", self.vis_w)
        form.addRow("Height", self.vis_h)
        form.addRow("Shift Y", self.vis_shift)

        self.gradient_start = QLineEdit()
        self.gradient_end = QLineEdit()
        pick_start = QPushButton("Pick")
        pick_end = QPushButton("Pick")
        pick_start.clicked.connect(lambda: self._pick_color(self.gradient_start))
        pick_end.clicked.connect(lambda: self._pick_color(self.gradient_end))
        form.addRow("Gradient start", self._row_with(self.gradient_start, pick_start))
        form.addRow("Gradient end", self._row_with(self.gradient_end, pick_end))

        layout.addLayout(form)

        buttons = QHBoxLayout()
        btn_center = QPushButton("Center")
        btn_top = QPushButton("Top")
        btn_bottom = QPushButton("Bottom")
        btn_stretch = QPushButton("Stretch width")
        btn_center.clicked.connect(self._set_center)
        btn_top.clicked.connect(lambda: self._set_vertical("top"))
        btn_bottom.clicked.connect(lambda: self._set_vertical("bottom"))
        btn_stretch.clicked.connect(self._stretch_width)
        buttons.addWidget(btn_center)
        buttons.addWidget(btn_top)
        buttons.addWidget(btn_bottom)
        buttons.addWidget(btn_stretch)
        layout.addLayout(buttons)

        self.vis_x.valueChanged.connect(lambda v: self._update_config("visualizer.x", v))
        self.vis_y.valueChanged.connect(lambda v: self._update_config("visualizer.y", v))
        self.vis_w.valueChanged.connect(lambda v: self._update_config("visualizer.width", v))
        self.vis_h.valueChanged.connect(lambda v: self._update_config("visualizer.height", v))
        self.vis_shift.valueChanged.connect(lambda v: self._update_config("visualizer.shift_y", v))
        self.gradient_start.textChanged.connect(lambda v: self._update_config("visualizer.gradient_start", v))
        self.gradient_end.textChanged.connect(lambda v: self._update_config("visualizer.gradient_end", v))

        layout.addStretch(1)
        self._load_visualizer_panel()
        return panel

    def _build_clock_panel(self):
        panel = QWidget()
        layout = QVBoxLayout(panel)
        form = QFormLayout()

        self.clock_enabled = QCheckBox()
        self.clock_color = QLineEdit()
        self.clock_opacity = QSpinBox()
        self.clock_opacity.setRange(0, 255)
        self.clock_font = QFontComboBox()
        self.clock_size = QDoubleSpinBox()
        self.clock_size.setRange(0.05, 1.0)
        self.clock_size.setSingleStep(0.01)
        self.clock_weight = QComboBox()
        self.clock_weight.addItems(["bold", "normal", "light"])
        self.clock_spacing = QDoubleSpinBox()
        self.clock_spacing.setRange(0.5, 2.0)
        self.clock_spacing.setSingleStep(0.1)
        self.clock_offset = QSpinBox()
        self.clock_offset.setRange(0, 2000)
        self.clock_hours = QLineEdit()
        self.clock_minutes = QLineEdit()

        pick_color = QPushButton("Pick")
        pick_color.clicked.connect(lambda: self._pick_color(self.clock_color))

        form.addRow("Enabled", self.clock_enabled)
        form.addRow("Color", self._row_with(self.clock_color, pick_color))
        form.addRow("Opacity", self.clock_opacity)
        form.addRow("Font", self.clock_font)
        form.addRow("Font size ratio", self.clock_size)
        form.addRow("Weight", self.clock_weight)
        form.addRow("Line spacing", self.clock_spacing)
        form.addRow("Vertical offset", self.clock_offset)
        form.addRow("Format hours", self.clock_hours)
        form.addRow("Format minutes", self.clock_minutes)

        layout.addLayout(form)
        layout.addStretch(1)

        self.clock_enabled.stateChanged.connect(lambda v: self._update_config("clock.enabled", bool(v)))
        self.clock_color.textChanged.connect(lambda v: self._update_config("clock.color", v))
        self.clock_opacity.valueChanged.connect(lambda v: self._update_config("clock.opacity", v))
        self.clock_font.currentFontChanged.connect(lambda f: self._update_config("clock.font_family", f.family()))
        self.clock_size.valueChanged.connect(lambda v: self._update_config("clock.font_size_ratio", v))
        self.clock_weight.currentTextChanged.connect(lambda v: self._update_config("clock.font_weight", v))
        self.clock_spacing.valueChanged.connect(lambda v: self._update_config("clock.line_spacing", v))
        self.clock_offset.valueChanged.connect(lambda v: self._update_config("clock.vertical_offset", v))
        self.clock_hours.textChanged.connect(lambda v: self._update_config("clock.format.hours", v))
        self.clock_minutes.textChanged.connect(lambda v: self._update_config("clock.format.minutes", v))

        self._load_clock_panel()
        return panel

    def _build_overlay_panel(self):
        panel = QWidget()
        layout = QVBoxLayout(panel)
        form = QFormLayout()

        self.overlay_enabled = QCheckBox()
        self.overlay_path = QLineEdit()
        self.overlay_scale = QComboBox()
        self.overlay_scale.addItems(["fit", "fill", "stretch"])

        pick = QPushButton("Browse")
        pick.clicked.connect(self._pick_overlay)

        form.addRow("Enabled", self.overlay_enabled)
        form.addRow("Image", self._row_with(self.overlay_path, pick))
        form.addRow("Scale mode", self.overlay_scale)

        layout.addLayout(form)
        layout.addStretch(1)

        self.overlay_enabled.stateChanged.connect(lambda v: self._update_config("overlay.enabled", bool(v)))
        self.overlay_path.textChanged.connect(lambda v: self._update_config("overlay.image", v))
        self.overlay_scale.currentTextChanged.connect(lambda v: self._update_config("overlay.scale_mode", v))

        self._load_overlay_panel()
        return panel

    def _build_audio_panel(self):
        panel = QWidget()
        layout = QVBoxLayout(panel)
        form = QFormLayout()

        self.audio_bar_count = QSpinBox()
        self.audio_bar_count.setRange(10, 512)
        self.audio_samplerate = QSpinBox()
        self.audio_samplerate.setRange(8000, 192000)
        self.audio_blocksize = QSpinBox()
        self.audio_blocksize.setRange(128, 8192)
        self.audio_buffer_blocks = QSpinBox()
        self.audio_buffer_blocks.setRange(1, 256)
        self.audio_smooth = QDoubleSpinBox()
        self.audio_smooth.setRange(0.0, 1.0)
        self.audio_smooth.setSingleStep(0.05)
        self.audio_change = QDoubleSpinBox()
        self.audio_change.setRange(0.0, 2.0)
        self.audio_change.setSingleStep(0.05)
        self.audio_noise = QDoubleSpinBox()
        self.audio_noise.setRange(0.0, 1.0)
        self.audio_noise.setSingleStep(0.01)
        self.audio_peak = QDoubleSpinBox()
        self.audio_peak.setRange(0.1, 5.0)
        self.audio_peak.setSingleStep(0.1)
        self.audio_avg = QSpinBox()
        self.audio_avg.setRange(1, 60)
        self.audio_mode = QComboBox()
        self.audio_mode.addItems(["linear", "bass_center", "bass_edges"])
        self.audio_fmin = QDoubleSpinBox()
        self.audio_fmin.setRange(20.0, 2000.0)
        self.audio_fmax = QDoubleSpinBox()
        self.audio_fmax.setRange(200.0, 20000.0)
        self.audio_cqt = QSpinBox()
        self.audio_cqt.setRange(1, 24)
        self.audio_bins = QSpinBox()
        self.audio_bins.setRange(6, 36)
        self.audio_acc_thr = QDoubleSpinBox()
        self.audio_acc_thr.setRange(1.0, 10.0)
        self.audio_acc_boost = QDoubleSpinBox()
        self.audio_acc_boost.setRange(1.0, 10.0)
        self.audio_backend = QComboBox()
        self.audio_backend.addItems(["internal", "glava"])

        form.addRow("Bars", self.audio_bar_count)
        form.addRow("Samplerate", self.audio_samplerate)
        form.addRow("Blocksize", self.audio_blocksize)
        form.addRow("Buffer blocks", self.audio_buffer_blocks)
        form.addRow("Smooth factor", self.audio_smooth)
        form.addRow("Max change speed", self.audio_change)
        form.addRow("Noise floor", self.audio_noise)
        form.addRow("Peak sharpness", self.audio_peak)
        form.addRow("Avg window", self.audio_avg)
        form.addRow("Mode", self.audio_mode)
        form.addRow("Fmin", self.audio_fmin)
        form.addRow("Fmax", self.audio_fmax)
        form.addRow("CQT bins/bar", self.audio_cqt)
        form.addRow("Bins/octave", self.audio_bins)
        form.addRow("Accent threshold", self.audio_acc_thr)
        form.addRow("Accent boost", self.audio_acc_boost)
        form.addRow("Backend", self.audio_backend)

        layout.addLayout(form)
        layout.addStretch(1)

        self.audio_bar_count.valueChanged.connect(lambda v: self._update_config("audio.bar_count", v))
        self.audio_samplerate.valueChanged.connect(lambda v: self._update_config("audio.samplerate", v))
        self.audio_blocksize.valueChanged.connect(lambda v: self._update_config("audio.blocksize", v))
        self.audio_buffer_blocks.valueChanged.connect(lambda v: self._update_config("audio.buffer_blocks", v))
        self.audio_smooth.valueChanged.connect(lambda v: self._update_config("audio.exp_smooth_factor", v))
        self.audio_change.valueChanged.connect(lambda v: self._update_config("audio.max_change_speed", v))
        self.audio_noise.valueChanged.connect(lambda v: self._update_config("audio.noise_floor", v))
        self.audio_peak.valueChanged.connect(lambda v: self._update_config("audio.peak_sharpness", v))
        self.audio_avg.valueChanged.connect(lambda v: self._update_config("audio.avg_window_size", v))
        self.audio_mode.currentTextChanged.connect(lambda v: self._update_config("audio.visualization_mode", v))
        self.audio_fmin.valueChanged.connect(lambda v: self._update_config("audio.fmin", v))
        self.audio_fmax.valueChanged.connect(lambda v: self._update_config("audio.fmax", v))
        self.audio_cqt.valueChanged.connect(lambda v: self._update_config("audio.cqt_bins_per_bar", v))
        self.audio_bins.valueChanged.connect(lambda v: self._update_config("audio.bins_per_octave", v))
        self.audio_acc_thr.valueChanged.connect(lambda v: self._update_config("audio.accent_threshold", v))
        self.audio_acc_boost.valueChanged.connect(lambda v: self._update_config("audio.accent_boost", v))
        self.audio_backend.currentTextChanged.connect(lambda v: self._update_config("audio.backend", v))

        self._load_audio_panel()
        return panel

    def _build_system_panel(self):
        panel = QWidget()
        layout = QVBoxLayout(panel)
        form = QFormLayout()

        self.platform_backend = QComboBox()
        self.platform_backend.addItems(["auto", "x11", "wayland"])
        self.wayland_layer = QComboBox()
        self.wayland_layer.addItems(["background", "bottom", "top", "overlay"])
        self.preview_mode = QComboBox()
        self.preview_mode.addItems(["fake", "live"])

        form.addRow("Platform backend", self.platform_backend)
        form.addRow("Wayland layer", self.wayland_layer)
        form.addRow("Preview mode", self.preview_mode)

        layout.addLayout(form)
        layout.addStretch(1)

        self.platform_backend.currentTextChanged.connect(lambda v: self._update_config("platform.backend", v))
        self.wayland_layer.currentTextChanged.connect(lambda v: self._update_config("platform.wayland_layer", v))
        self.preview_mode.currentTextChanged.connect(lambda v: self._update_config("preview.mode", v))

        self._load_system_panel()
        return panel

    def _build_presets_panel(self):
        panel = QWidget()
        layout = QVBoxLayout(panel)

        self.preset_name = QLineEdit()
        save_btn = QPushButton("Save preset")
        load_btn = QPushButton("Load preset")
        self.preset_list = QListWidget()

        save_btn.clicked.connect(self._save_preset)
        load_btn.clicked.connect(self._load_preset)

        layout.addWidget(QLabel("Preset name"))
        layout.addWidget(self.preset_name)
        layout.addWidget(save_btn)
        layout.addWidget(QLabel("Presets"))
        layout.addWidget(self.preset_list, 1)
        layout.addWidget(load_btn)

        self._refresh_presets()
        return panel

    def _row_with(self, field, button):
        wrapper = QWidget()
        layout = QHBoxLayout(wrapper)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(field, 1)
        layout.addWidget(button)
        return wrapper

    def _pick_color(self, line_edit):
        color = QColor(line_edit.text() or "#FFFFFF")
        picked = QColorDialog.getColor(color, self, "Select color")
        if picked.isValid():
            line_edit.setText(picked.name())

    def _pick_overlay(self):
        file_path, _ = QFileDialog.getOpenFileName(self, "Select overlay image", "", "Images (*.png *.jpg *.jpeg *.bmp)")
        if not file_path:
            return
        manager = OverlayManager(str(self.config_path))
        manager.process(file_path)
        self._reload_config()

    def _update_config(self, path, value):
        _set_path(self.config, path, value)
        if path.startswith("audio.") and _get_path(self.config, "preview.mode", "fake") == "live":
            self._stop_live_preview()
        self.preview.set_config(self.config)
        self.status.setText(f"Updated {path}")
        self._schedule_save()

    def _on_preview_rect_changed(self, x, y, w, h):
        _set_path(self.config, "visualizer.x", x)
        _set_path(self.config, "visualizer.y", y)
        _set_path(self.config, "visualizer.width", w)
        _set_path(self.config, "visualizer.height", h)
        self._load_visualizer_panel()
        self.preview.set_config(self.config)
        self._schedule_save()

    def _set_center(self):
        screen = self.preview.screen_size
        w = _get_path(self.config, "visualizer.width", 0)
        h = _get_path(self.config, "visualizer.height", 0)
        x = max(0, int((screen.width() - w) / 2))
        y = max(0, int((screen.height() - h) / 2))
        self._on_preview_rect_changed(x, y, w, h)

    def _set_vertical(self, mode):
        screen = self.preview.screen_size
        x = _get_path(self.config, "visualizer.x", 0)
        w = _get_path(self.config, "visualizer.width", 0)
        h = _get_path(self.config, "visualizer.height", 0)
        if mode == "top":
            y = 0
        else:
            y = max(0, screen.height() - h)
        self._on_preview_rect_changed(x, y, w, h)

    def _stretch_width(self):
        screen = self.preview.screen_size
        y = _get_path(self.config, "visualizer.y", 0)
        h = _get_path(self.config, "visualizer.height", 0)
        self._on_preview_rect_changed(0, y, screen.width(), h)

    def _load_visualizer_panel(self):
        self.vis_x.blockSignals(True)
        self.vis_y.blockSignals(True)
        self.vis_w.blockSignals(True)
        self.vis_h.blockSignals(True)
        self.vis_shift.blockSignals(True)
        self.gradient_start.blockSignals(True)
        self.gradient_end.blockSignals(True)

        self.vis_x.setValue(_get_path(self.config, "visualizer.x", 0))
        self.vis_y.setValue(_get_path(self.config, "visualizer.y", 0))
        self.vis_w.setValue(_get_path(self.config, "visualizer.width", 0))
        self.vis_h.setValue(_get_path(self.config, "visualizer.height", 0))
        self.vis_shift.setValue(_get_path(self.config, "visualizer.shift_y", 0))
        self.gradient_start.setText(_get_path(self.config, "visualizer.gradient_start", "#DE726E"))
        self.gradient_end.setText(_get_path(self.config, "visualizer.gradient_end", "#F0B781"))

        self.vis_x.blockSignals(False)
        self.vis_y.blockSignals(False)
        self.vis_w.blockSignals(False)
        self.vis_h.blockSignals(False)
        self.vis_shift.blockSignals(False)
        self.gradient_start.blockSignals(False)
        self.gradient_end.blockSignals(False)

    def _load_clock_panel(self):
        self.clock_enabled.blockSignals(True)
        self.clock_color.blockSignals(True)
        self.clock_opacity.blockSignals(True)
        self.clock_font.blockSignals(True)
        self.clock_size.blockSignals(True)
        self.clock_weight.blockSignals(True)
        self.clock_spacing.blockSignals(True)
        self.clock_offset.blockSignals(True)
        self.clock_hours.blockSignals(True)
        self.clock_minutes.blockSignals(True)

        self.clock_enabled.setChecked(_get_path(self.config, "clock.enabled", True))
        self.clock_color.setText(_get_path(self.config, "clock.color", "#FFFFFF"))
        self.clock_opacity.setValue(_get_path(self.config, "clock.opacity", 220))
        self.clock_font.setCurrentFont(QFont(_get_path(self.config, "clock.font_family", "Helvetica")))
        self.clock_size.setValue(_get_path(self.config, "clock.font_size_ratio", 0.2))
        self.clock_weight.setCurrentText(_get_path(self.config, "clock.font_weight", "bold"))
        self.clock_spacing.setValue(_get_path(self.config, "clock.line_spacing", 1.0))
        self.clock_offset.setValue(_get_path(self.config, "clock.vertical_offset", 10))
        self.clock_hours.setText(_get_path(self.config, "clock.format.hours", "hh"))
        self.clock_minutes.setText(_get_path(self.config, "clock.format.minutes", "mm"))

        self.clock_enabled.blockSignals(False)
        self.clock_color.blockSignals(False)
        self.clock_opacity.blockSignals(False)
        self.clock_font.blockSignals(False)
        self.clock_size.blockSignals(False)
        self.clock_weight.blockSignals(False)
        self.clock_spacing.blockSignals(False)
        self.clock_offset.blockSignals(False)
        self.clock_hours.blockSignals(False)
        self.clock_minutes.blockSignals(False)

    def _load_overlay_panel(self):
        self.overlay_enabled.blockSignals(True)
        self.overlay_path.blockSignals(True)
        self.overlay_scale.blockSignals(True)
        self.overlay_enabled.setChecked(_get_path(self.config, "overlay.enabled", True))
        self.overlay_path.setText(_get_path(self.config, "overlay.image", ""))
        self.overlay_scale.setCurrentText(_get_path(self.config, "overlay.scale_mode", "fill"))
        self.overlay_enabled.blockSignals(False)
        self.overlay_path.blockSignals(False)
        self.overlay_scale.blockSignals(False)

    def _load_audio_panel(self):
        self.audio_bar_count.blockSignals(True)
        self.audio_samplerate.blockSignals(True)
        self.audio_blocksize.blockSignals(True)
        self.audio_buffer_blocks.blockSignals(True)
        self.audio_smooth.blockSignals(True)
        self.audio_change.blockSignals(True)
        self.audio_noise.blockSignals(True)
        self.audio_peak.blockSignals(True)
        self.audio_avg.blockSignals(True)
        self.audio_mode.blockSignals(True)
        self.audio_fmin.blockSignals(True)
        self.audio_fmax.blockSignals(True)
        self.audio_cqt.blockSignals(True)
        self.audio_bins.blockSignals(True)
        self.audio_acc_thr.blockSignals(True)
        self.audio_acc_boost.blockSignals(True)
        self.audio_backend.blockSignals(True)

        self.audio_bar_count.setValue(_get_path(self.config, "audio.bar_count", 100))
        self.audio_samplerate.setValue(_get_path(self.config, "audio.samplerate", 44100))
        self.audio_blocksize.setValue(_get_path(self.config, "audio.blocksize", 1024))
        self.audio_buffer_blocks.setValue(_get_path(self.config, "audio.buffer_blocks", 32))
        self.audio_smooth.setValue(_get_path(self.config, "audio.exp_smooth_factor", 0.3))
        self.audio_change.setValue(_get_path(self.config, "audio.max_change_speed", 0.6))
        self.audio_noise.setValue(_get_path(self.config, "audio.noise_floor", 0.02))
        self.audio_peak.setValue(_get_path(self.config, "audio.peak_sharpness", 2.0))
        self.audio_avg.setValue(_get_path(self.config, "audio.avg_window_size", 5))
        self.audio_mode.setCurrentText(_get_path(self.config, "audio.visualization_mode", "bass_center"))
        self.audio_fmin.setValue(_get_path(self.config, "audio.fmin", 100.0))
        self.audio_fmax.setValue(_get_path(self.config, "audio.fmax", 6000.0))
        self.audio_cqt.setValue(_get_path(self.config, "audio.cqt_bins_per_bar", 3))
        self.audio_bins.setValue(_get_path(self.config, "audio.bins_per_octave", 12))
        self.audio_acc_thr.setValue(_get_path(self.config, "audio.accent_threshold", 5.0))
        self.audio_acc_boost.setValue(_get_path(self.config, "audio.accent_boost", 5.0))
        self.audio_backend.setCurrentText(_get_path(self.config, "audio.backend", "internal"))

        self.audio_bar_count.blockSignals(False)
        self.audio_samplerate.blockSignals(False)
        self.audio_blocksize.blockSignals(False)
        self.audio_buffer_blocks.blockSignals(False)
        self.audio_smooth.blockSignals(False)
        self.audio_change.blockSignals(False)
        self.audio_noise.blockSignals(False)
        self.audio_peak.blockSignals(False)
        self.audio_avg.blockSignals(False)
        self.audio_mode.blockSignals(False)
        self.audio_fmin.blockSignals(False)
        self.audio_fmax.blockSignals(False)
        self.audio_cqt.blockSignals(False)
        self.audio_bins.blockSignals(False)
        self.audio_acc_thr.blockSignals(False)
        self.audio_acc_boost.blockSignals(False)
        self.audio_backend.blockSignals(False)

    def _load_system_panel(self):
        self.platform_backend.blockSignals(True)
        self.wayland_layer.blockSignals(True)
        self.preview_mode.blockSignals(True)

        self.platform_backend.setCurrentText(_get_path(self.config, "platform.backend", "auto"))
        self.wayland_layer.setCurrentText(_get_path(self.config, "platform.wayland_layer", "background"))
        self.preview_mode.setCurrentText(_get_path(self.config, "preview.mode", "fake"))

        self.platform_backend.blockSignals(False)
        self.wayland_layer.blockSignals(False)
        self.preview_mode.blockSignals(False)

    def _save_config(self):
        self._saving = True
        save_config(self.config_path, self.config)
        self._saving = False
        self.status.setText("Config saved.")

    def _reload_config(self):
        self.config = load_config(self.config_path)
        self.preview.set_config(self.config)
        self._load_visualizer_panel()
        self._load_clock_panel()
        self._load_overlay_panel()
        self._load_audio_panel()
        self._load_system_panel()
        self._refresh_presets()
        self.status.setText("Config reloaded.")

    def _presets_dir(self):
        root = Path(__file__).resolve().parent
        presets_dir = root / "presets"
        presets_dir.mkdir(exist_ok=True)
        return presets_dir

    def _refresh_presets(self):
        self.preset_list.clear()
        for path in sorted(self._presets_dir().glob("*.yaml")):
            self.preset_list.addItem(path.stem)

    def _save_preset(self):
        name = self.preset_name.text().strip()
        if not name:
            return
        path = self._presets_dir() / f"{name}.yaml"
        save_config(path, self.config)
        self._refresh_presets()
        self.status.setText(f"Preset saved: {name}")

    def _load_preset(self):
        item = self.preset_list.currentItem()
        if not item:
            return
        path = self._presets_dir() / f"{item.text()}.yaml"
        if not path.exists():
            return
        self.config = load_config(path)
        self.preview.set_config(self.config)
        self._load_visualizer_panel()
        self._load_clock_panel()
        self._load_overlay_panel()
        self._load_audio_panel()
        self._load_system_panel()
        self.status.setText(f"Preset loaded: {item.text()}")

    def closeEvent(self, event):
        self._stop_live_preview()
        super().closeEvent(event)


def run_configurator(config_path: Path):
    app = QApplication(sys.argv)
    window = ConfiguratorWindow(config_path)
    window.show()
    sys.exit(app.exec_())
