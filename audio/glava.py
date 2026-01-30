import numpy as np

from .internal import InternalAudioProcessor


class GlavaAudioProcessor:
    """
    Экспериментальный backend в стиле glava.
    Пока использует внутренний pipeline, но применяет доп. эквализацию.
    """

    def __init__(self, **kwargs):
        self._inner = InternalAudioProcessor(**kwargs)
        self._eq_curve = None

    def _ensure_curve(self, size):
        if self._eq_curve is not None and self._eq_curve.size == size:
            return
        x = np.linspace(0.0, 1.0, size)
        # слегка приподнимаем басы/верха, чтобы отличалось от internal
        curve = 0.8 + 0.4 * np.sin(np.pi * x)
        self._eq_curve = curve.astype(float)

    def audio_callback(self, indata, frames, time, status):
        return self._inner.audio_callback(indata, frames, time, status)

    def get_fft_data(self):
        data = self._inner.get_fft_data()
        self._ensure_curve(data.size)
        shaped = np.clip(data * self._eq_curve, 0.0, 1.0)
        return shaped
