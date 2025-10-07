# audio_processor.py
"""
AudioProcessor — realtime audio -> визуальные полосы (bar_count)
Реализация использует librosa.cqt (Constant-Q Transform), возвращая
массив amplitudes в диапазоне [0..1] готовый к отрисовке.
С детектором акцентов для реакции только на выраженные звуки.
"""

from collections import deque
import numpy as np
import librosa
import threading
import math
import warnings

class AudioProcessor:
    def __init__(
        self,
        bar_count: int = 64,
        samplerate: int = 44100,
        blocksize: int = 1024,
        buffer_blocks: int = 32,
        exp_smooth_factor: float = 0.4,
        max_change_speed: float = 0.5,
        noise_floor: float = 0.02,
        peak_sharpness: float = 1.4,
        avg_window_size: int = 5,
        visualization_mode: str = "linear",
        fmin: float = 100.0,
        fmax: float = 6000.0,
        cqt_bins_per_bar: int = 3,
        bins_per_octave: int = 12,
        accent_threshold: float = 1.8,  # Множитель для детекции акцента
        accent_boost: float = 2.0,       # Насколько усиливать акценты
    ):
        # параметры интерфейса
        self.bar_count = int(bar_count)
        self.samplerate = int(samplerate)
        self.blocksize = int(blocksize)
        self.buffer_blocks = int(max(1, buffer_blocks))

        # алгоритмические параметры
        self.exp_smooth_factor = float(exp_smooth_factor)
        self.max_change_speed = float(max_change_speed)
        self.noise_floor = float(noise_floor)
        self.peak_sharpness = float(peak_sharpness)
        self.avg_window_size = int(max(1, avg_window_size))

        # визуализация
        self.visualization_mode = visualization_mode

        # частотные границы для CQT
        self.fmin = float(fmin)
        self.fmax = float(fmax)
        self.bins_per_octave = int(bins_per_octave)
        self.cqt_bins_per_bar = int(max(1, cqt_bins_per_bar))

        # ПАРАМЕТРЫ ДЕТЕКТОРА АКЦЕНТОВ
        self.accent_threshold = float(accent_threshold)
        self.accent_boost = float(accent_boost)
        self.energy_history = deque(maxlen=20)
        self.last_accent_time = 0
        self.accent_cooldown = 5  # Минимум 5 кадров между акцентами

        # внутренние структуры
        self.fft_data = np.zeros(self.bar_count, dtype=float)
        self.fft_history = deque(maxlen=self.avg_window_size)
        for _ in range(self.avg_window_size):
            self.fft_history.append(np.zeros(self.bar_count, dtype=float))

        self.max_history = deque(maxlen=60)
        self.audio_buffer = np.zeros(0, dtype=float)
        self.buffer_size = self.blocksize * self.buffer_blocks

        # precompute CQT config
        if self.fmax <= self.fmin:
            raise ValueError("fmax must be greater than fmin")
        self.n_octaves = math.ceil(math.log(self.fmax / self.fmin, 2.0))
        self.cqt_n_bins = max(self.bar_count * self.cqt_bins_per_bar, self.bins_per_octave * self.n_octaves)
        self.cqt_n_bins = int(self.cqt_n_bins)
        self.hop_length = max(256, self.blocksize // 2)

        # блокировка для потокобезопасности
        self._lock = threading.Lock()
        self._warned_cqt = False
        self._frame_counter = 0

    def audio_callback(self, indata, frames, time, status):
        if status:
            try:
                print(f"Audio status: {status}")
            except Exception:
                pass

        self._frame_counter += 1

        # моно конверсия
        if indata.ndim == 1:
            audio_chunk = indata.astype(float)
        else:
            audio_chunk = np.mean(indata, axis=1).astype(float)

        # ДЕТЕКТОР ОБЩЕЙ ЭНЕРГИИ (для акцентов)
        current_energy = np.sqrt(np.mean(audio_chunk ** 2))
        self.energy_history.append(current_energy)
        avg_energy = np.mean(self.energy_history) if len(self.energy_history) > 0 else 0.01
        
        # Детекция акцента: текущая энергия >> средней
        is_accent = False
        accent_multiplier = 1.0  # Множитель для усиления при акценте
        
        if current_energy > avg_energy * self.accent_threshold:
            if self._frame_counter - self.last_accent_time > self.accent_cooldown:
                is_accent = True
                self.last_accent_time = self._frame_counter
                # Вычисляем насколько сильный акцент (1.0 до accent_boost)
                accent_strength = min((current_energy / avg_energy) / self.accent_threshold, 3.0)
                accent_multiplier = 1.0 + (self.accent_boost - 1.0) * accent_strength

        # аккумуляция буфера
        self.audio_buffer = np.concatenate([self.audio_buffer, audio_chunk])

        if len(self.audio_buffer) < max(self.buffer_size, self.blocksize):
            analysis_data = self.audio_buffer.copy()
        else:
            analysis_data = self.audio_buffer[-self.buffer_size:].copy()
            self.audio_buffer = self.audio_buffer[-self.buffer_size:]

        if len(analysis_data) < 16:
            analysis_data = np.pad(analysis_data, (0, 16 - len(analysis_data)), mode="constant")

        # нормализация
        if np.max(np.abs(analysis_data)) > 0:
            analysis_data = analysis_data / (np.max(np.abs(analysis_data)) + 1e-9)

        # CQT вычисление
        try:
            safe_fmax = min(self.fmax, self.samplerate / 2 - 100)
            n_octaves = math.log2(safe_fmax / self.fmin)
            safe_bins = int(self.bins_per_octave * n_octaves)

            cqt = librosa.cqt(
                y=analysis_data,
                sr=self.samplerate,
                hop_length=self.hop_length,
                fmin=self.fmin,
                n_bins=safe_bins,
                bins_per_octave=self.bins_per_octave,
                filter_scale=1.0
            )
            
            if cqt.size == 0 or np.allclose(cqt, 0):
                return

            if cqt.ndim == 2 and cqt.shape[1] > 0:
                cqt_frame = np.abs(cqt[:, -1])
            else:
                cqt_frame = np.abs(cqt).reshape(-1)
                
        except Exception as e:
            if not self._warned_cqt:
                warnings.warn(f"librosa.cqt failed: {e}")
                self._warned_cqt = True
            cqt_frame = np.zeros(self.cqt_n_bins, dtype=float)

        # преобразование в dB и нормализация
        eps = 1e-10
        cqt_power = cqt_frame ** 2
        cqt_db = librosa.power_to_db(cqt_power, ref=np.max, top_db=80.0)
        
        if np.isfinite(cqt_db).any():
            cmin = np.nanmin(cqt_db)
            cmax = np.nanmax(cqt_db)
            if cmax > cmin:
                normalized_bins = (cqt_db - cmin) / (cmax - cmin + eps)
            else:
                normalized_bins = np.zeros_like(cqt_db)
        else:
            normalized_bins = np.zeros_like(cqt_db)

        # агрегация bins -> bars
        total_bins = normalized_bins.shape[0]
        if total_bins < self.bar_count:
            padded = np.pad(normalized_bins, (0, self.bar_count - total_bins), mode="constant")
            grouped = padded[:self.bar_count]
        else:
            idx = np.linspace(0, total_bins, num=self.bar_count + 1, dtype=int)
            grouped = np.zeros(self.bar_count, dtype=float)
            for i in range(self.bar_count):
                a, b = idx[i], idx[i+1]
                if b > a:
                    grouped[i] = np.mean(normalized_bins[a:b])

        # УСИЛЕННЫЙ noise floor - убираем гул
        grouped[grouped < self.noise_floor * 2] = 0.0

        # Если акцент - усиливаем сигнал
        if is_accent:
            grouped = grouped * self.accent_boost
            grouped = np.clip(grouped, 0, 1.0)

        # усиление пиков (контраст) - УВЕЛИЧЕН для чёткости
        boosted = np.power(grouped, self.peak_sharpness * 1.5)
        new_data = np.sqrt(boosted)

        # режимы визуализации
        if self.visualization_mode == "bass_center":
            new_data = self._apply_bass_center(new_data)
        elif self.visualization_mode == "bass_edges":
            new_data = self._apply_bass_edges(new_data)

        # сглаживание
        with self._lock:
            smoothed = (1 - self.exp_smooth_factor) * self.fft_data + self.exp_smooth_factor * new_data
            delta = np.clip(smoothed - self.fft_data, -self.max_change_speed, self.max_change_speed)
            updated = self.fft_data + delta

            self.fft_history.append(updated)
            averaged = np.mean(self.fft_history, axis=0)

            # адаптивная нормализация
            max_val = np.max(averaged) if np.max(averaged) > 0 else 0.0
            self.max_history.append(max_val + 1e-9)
            historical_scale = np.percentile(self.max_history, 85) if len(self.max_history) > 0 else 1.0
            if historical_scale > 0.2:
                averaged = averaged / historical_scale

            # УСИЛЕННОЕ удаление шумов
            averaged[averaged < self.noise_floor * 1.5] = 0.0
            averaged = np.clip(averaged, 0.0, 1.0)

            self.fft_data = averaged

    def _apply_bass_center(self, data: np.ndarray) -> np.ndarray:
        """Басы в центре, высокие по краям (зеркально)."""
        bass_count = max(4, self.bar_count // 12)
        side_count = (self.bar_count - bass_count) // 2
        bass_data = data[:bass_count]
        remaining = data[bass_count: bass_count + side_count]
        left = remaining[::-1]
        right = remaining
        result = np.concatenate([left, bass_data, right])
        if result.size < self.bar_count:
            result = np.pad(result, (0, self.bar_count - result.size), mode="constant")
        return result[:self.bar_count]

    def _apply_bass_edges(self, data: np.ndarray) -> np.ndarray:
        """Басы по краям, высокие в центре (зеркально)."""
        bass_count = max(4, self.bar_count // 12)
        center_count = self.bar_count - bass_count * 2
        bass_data = data[:bass_count]
        center_data = data[bass_count: bass_count + center_count]
        right_bass = bass_data[::-1]
        result = np.concatenate([bass_data, center_data, right_bass])
        if result.size < self.bar_count:
            result = np.pad(result, (0, self.bar_count - result.size), mode="constant")
        return result[:self.bar_count]

    def get_fft_data(self) -> np.ndarray:
        """Безопасно вернуть текущие данные для рисования (копия)."""
        with self._lock:
            return self.fft_data.copy()