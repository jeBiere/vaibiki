import numpy as np
from scipy.fft import fft
from collections import deque

class AudioProcessor:
    def __init__(self, config):
        self.bar_count = config["bar_count"]
        self.exp_smooth_factor = config["exp_smooth_factor"]
        self.max_change_speed = config["max_change_speed"]
        self.noise_floor = config["noise_floor"]
        self.peak_sharpness = config["peak_sharpness"]
        self.avg_window_size = config["avg_window_size"]

        self.fft_data = np.zeros(self.bar_count)
        self.fft_history = deque(maxlen=self.avg_window_size)
        for _ in range(self.avg_window_size):
            self.fft_history.append(np.zeros(self.bar_count))

        # Параметры FFT
        self.raw_fft_size = 512
        self.freq_crop_size = 100

    def audio_callback(self, indata, frames, time, status):
        if status:
            print(status)

        audio_data = indata[:, 0]
        fft_values = np.abs(fft(audio_data))[:self.raw_fft_size]
        cropped = fft_values[:self.freq_crop_size]

        # Интерполяция под количество полос визуализации
        x_old = np.linspace(0, 1, len(cropped))
        x_new = np.linspace(0, 1, self.bar_count)
        interpolated = np.interp(x_new, x_old, cropped)

        # Нормализация и усиление пиков
        fft_norm = interpolated / (np.max(interpolated) + 1e-6)
        boosted = np.power(fft_norm, self.peak_sharpness)
        new_data = np.sqrt(boosted)

        # Экспоненциальное сглаживание с ограничением изменения
        smoothed = (1 - self.exp_smooth_factor) * self.fft_data + self.exp_smooth_factor * new_data
        delta = np.clip(smoothed - self.fft_data, -self.max_change_speed, self.max_change_speed)
        updated = self.fft_data + delta

        # Скользящее усреднение
        self.fft_history.append(updated)
        averaged = np.mean(self.fft_history, axis=0)

        # Удаление шумов
        averaged[averaged < self.noise_floor] = 0.0

        self.fft_data = averaged

    def get_fft_data(self):
        return self.fft_data
