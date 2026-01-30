import copy
import yaml


DEFAULT_CONFIG = {
    "visualizer": {
        "x": 0,
        "y": 0,
        "width": 1280,
        "height": 360,
        "shift_y": 0,
        "gradient_start": "#DE726E",
        "gradient_end": "#F0B781",
    },
    "clock": {
        "enabled": True,
        "color": "#FFFFFF",
        "opacity": 220,
        "font_family": "Helvetica",
        "font_size_ratio": 0.2,
        "font_weight": "bold",
        "line_spacing": 1.0,
        "vertical_offset": 10,
        "format": {"hours": "hh", "minutes": "mm"},
    },
    "overlay": {
        "enabled": True,
        "image": "assets/new.png",
        "scale_mode": "fill",
    },
    "audio": {
        "bar_count": 100,
        "samplerate": 44100,
        "blocksize": 1024,
        "buffer_blocks": 32,
        "exp_smooth_factor": 0.3,
        "max_change_speed": 0.6,
        "noise_floor": 0.02,
        "peak_sharpness": 2.0,
        "avg_window_size": 5,
        "visualization_mode": "bass_center",
        "fmin": 100.0,
        "fmax": 6000.0,
        "cqt_bins_per_bar": 3,
        "bins_per_octave": 12,
        "accent_threshold": 5.0,
        "accent_boost": 5.0,
        "backend": "internal",
    },
    "platform": {
        "backend": "auto",
        "wayland_layer": "background",
    },
    "preview": {
        "mode": "fake",
    },
}


def _deep_update(target, src):
    for key, value in src.items():
        if isinstance(value, dict) and isinstance(target.get(key), dict):
            _deep_update(target[key], value)
        else:
            target[key] = value


def normalize_config(raw_config):
    config = copy.deepcopy(DEFAULT_CONFIG)
    if not raw_config:
        return config

    normalized = copy.deepcopy(raw_config)

    # migrate legacy flat keys into new structure
    if "audio" not in normalized:
        audio = {}
        for key in (
            "bar_count",
            "samplerate",
            "blocksize",
            "buffer_blocks",
            "exp_smooth_factor",
            "max_change_speed",
            "noise_floor",
            "peak_sharpness",
            "avg_window_size",
            "visualization_mode",
            "fmin",
            "fmax",
            "cqt_bins_per_bar",
            "bins_per_octave",
            "accent_threshold",
            "accent_boost",
            "backend",
        ):
            if key in normalized:
                audio[key] = normalized.pop(key)
        if audio:
            normalized["audio"] = audio

    if "overlay" not in normalized:
        overlay = {}
        if "overlay_enabled" in normalized:
            overlay["enabled"] = normalized.pop("overlay_enabled")
        if "overlay_image" in normalized:
            overlay["image"] = normalized.pop("overlay_image")
        if overlay:
            overlay.setdefault("scale_mode", "fill")
            normalized["overlay"] = overlay

    if "visualizer" in normalized:
        normalized["visualizer"] = dict(normalized["visualizer"])

    _deep_update(config, normalized)
    return config


def load_config(path):
    with open(path, "r", encoding="utf-8") as f:
        return normalize_config(yaml.safe_load(f))


def save_config(path, config):
    with open(path, "w", encoding="utf-8") as f:
        yaml.dump(config, f, default_flow_style=False, allow_unicode=True)
