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

        # ============= НАСТРОЙКА РЕЖИМА ВИЗУАЛИЗАЦИИ =============
        # "linear" - линейный (басы слева, высокие справа)
        # "bass_center" - зеркальный, басы в центре
        # "bass_edges" - зеркальный, басы по краям (высокие в центре)
        self.visualization_mode = config.get("visualization_mode", "bass_center")
        # ==========================================================

        self.fft_data = np.zeros(self.bar_count)
        self.fft_history = deque(maxlen=self.avg_window_size)
        for _ in range(self.avg_window_size):
            self.fft_history.append(np.zeros(self.bar_count))

        # Параметры FFT
        self.raw_fft_size = 100
        self.freq_crop_size = 50

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

        # ============= ПРИМЕНЯЕМ РЕЖИМ ВИЗУАЛИЗАЦИИ =============
        if self.visualization_mode == "bass_center":
            # Басы в центре, высокие по краям (зеркально)
            # [высокие...средние] [БАСЫ] [средние...высокие]
            new_data = self._apply_bass_center(new_data)
        elif self.visualization_mode == "bass_edges":
            # Басы по краям, высокие в центре (зеркально)
            # [БАСЫ] [средние...высокие...средние] [БАСЫ]
            new_data = self._apply_bass_edges(new_data)
        # Если "linear" - ничего не делаем, оставляем как есть
        # ========================================================

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

    def _apply_bass_center(self, data):
        """
        Басы в центре, высокие по краям (зеркально)
        Исходные данные: [низкие -> высокие]
        Результат: [высокие реверс, средние реверс] [низкие] [средние, высокие]
        """
        # Определяем сколько полос отдать басам (примерно 10%)
        bass_count = max(6, self.bar_count // 16)
        side_count = (self.bar_count - bass_count) // 2
        
        # Берём басы из начала массива
        bass_data = data[:bass_count]
        
        # Остальное - средние и высокие частоты
        remaining = data[bass_count:]
        
        # Берём нужное количество для одной стороны
        side_data = remaining[:side_count]
        
        # Создаём зеркальную структуру
        result = np.concatenate([
            side_data[::-1],  # Левая сторона (реверс)
            bass_data,        # Центр (басы)
            side_data         # Правая сторона
        ])
        
        # Если длина не совпадает, подгоняем
        if len(result) < self.bar_count:
            result = np.concatenate([result, np.zeros(self.bar_count - len(result))])
        elif len(result) > self.bar_count:
            result = result[:self.bar_count]
            
        return result

    def _apply_bass_edges(self, data):
        """
        Басы по краям, высокие в центре (зеркально)
        Исходные данные: [низкие -> высокие]
        Результат: [низкие] [средние, высокие, средние] [низкие]
        """
        # Определяем сколько полос отдать басам на каждый край
        bass_count = max(6, self.bar_count // 16)
        center_count = self.bar_count - bass_count * 2
        
        # Басы - из начала
        bass_data = data[:bass_count]
        
        # Средние и высокие - остальное
        mid_high_data = data[bass_count:]
        
        # Берём нужное количество для центра
        center_data = mid_high_data[:center_count]
        
        # Создаём структуру с басами по краям
        result = np.concatenate([
            bass_data,        # Левый край (басы)
            center_data,      # Центр (средние и высокие)
            bass_data[::-1]   # Правый край (басы реверс)
        ])
        
        # Подгоняем длину
        if len(result) < self.bar_count:
            result = np.concatenate([result, np.zeros(self.bar_count - len(result))])
        elif len(result) > self.bar_count:
            result = result[:self.bar_count]
            
        return result

    def get_fft_data(self):
        return self.fft_data