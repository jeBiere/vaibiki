# audio_processor.py
"""
AudioProcessor — realtime audio -> визуальные полосы (bar_count)
Реализация использует librosa.cqt (Constant-Q Transform), возвращая
массив amplitudes в диапазоне [0..1] готовый к отрисовке.

API:
    p = AudioProcessor(bar_count=64, samplerate=44100, ...)
    # в аудио-callback:
    p.audio_callback(indata, frames, time, status)
    # в GUI:
    bars = p.get_fft_data()  # numpy array shape (bar_count,)
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
        visualization_mode: str = "linear",  # "linear" | "bass_center" | "bass_edges"
        fmin: float = 100.0,
        fmax: float = 6000.0,
        cqt_bins_per_bar: int = 3,  # internal resolution: how many CQT bins per output bar
        bins_per_octave: int = 12,  # semitone resolution
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

        # внутренние структуры
        self.fft_data = np.zeros(self.bar_count, dtype=float)
        self.fft_history = deque(maxlen=self.avg_window_size)
        for _ in range(self.avg_window_size):
            self.fft_history.append(np.zeros(self.bar_count, dtype=float))

        self.max_history = deque(maxlen=60)
        self.audio_buffer = np.zeros(0, dtype=float)
        self.buffer_size = self.blocksize * self.buffer_blocks

        # precompute CQT config (n_bins)
        # выберем количество октав, покрывающих fmin..fmax
        if self.fmax <= self.fmin:
            raise ValueError("fmax must be greater than fmin")
        self.n_octaves = math.ceil(math.log(self.fmax / self.fmin, 2.0))
        # n_bins — внутреннее разрешение CQT
        self.cqt_n_bins = max(self.bar_count * self.cqt_bins_per_bar, self.bins_per_octave * self.n_octaves)
        # округлим вверх до целого
        self.cqt_n_bins = int(self.cqt_n_bins)

        # hop length — сколько сэмплов между вычислениями CQT.
        # Для реалтайма выгодно не делать hop слишком маленьким.
        # Подбор: блокsize примерно = 1024 -> hop_length = 512 (или blocksize // 2)
        self.hop_length = max(256, self.blocksize // 2)

        # блокировка для потокобезопасного чтения/записи fft_data
        self._lock = threading.Lock()

        # безопасный флаг для отключения повторных вызовов CQT если библиотека выдает предупреждения
        self._warned_cqt = False

    def audio_callback(self, indata, frames, time, status):
        """
        Ожидаемый вход: indata — numpy array shape (frames, channels)
        Эта функция должна вызываться из аудио-callback (например, sounddevice).
        """
        if status:
            # не ломаем поток — просто логируем
            try:
                print(f"Audio status: {status}")
            except Exception:
                pass

        # ожидаем моно (берём первый канал) — если стерео, берём среднее
        if indata.ndim == 1:
            audio_chunk = indata.astype(float)
        else:
            # безопасное снижение до моно: среднее двух каналов
            audio_chunk = np.mean(indata, axis=1).astype(float)

        # аккумулируем в буфер
        self.audio_buffer = np.concatenate([self.audio_buffer, audio_chunk])

        # если буфер не набрался — всё ещё можно делать анализ по тому что есть
        if len(self.audio_buffer) < max(self.buffer_size, self.blocksize):
            analysis_data = self.audio_buffer.copy()
        else:
            analysis_data = self.audio_buffer[-self.buffer_size:].copy()
            # сохраняем последние buffer_size, чтобы не расти без конца
            self.audio_buffer = self.audio_buffer[-self.buffer_size:]

        # если сигнал очень короткий — pad zeros (librosa требует минимум окон)
        if len(analysis_data) < 16:
            analysis_data = np.pad(analysis_data, (0, 16 - len(analysis_data)), mode="constant")

        # нормализуем немного уровень для численной стабильности
        if np.max(np.abs(analysis_data)) > 0:
            analysis_data = analysis_data / (np.max(np.abs(analysis_data)) + 1e-9)

        # вычисляем CQT (мощность)
        try:
            # гарантируем, что fmax не превышает Nyquist (sr / 2)
            safe_fmax = min(self.fmax, self.samplerate / 2 - 100)
            # пересчитаем допустимое количество бинов
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
            # если librosa не успела вернуть спектр, просто пропускаем кадр
                return

            # cqt.shape -> (n_bins, n_frames). Берём последний кадр (самый свежий)
            if cqt.ndim == 2 and cqt.shape[1] > 0:
                cqt_frame = np.abs(cqt[:, -1])
            else:
                cqt_frame = np.abs(cqt).reshape(-1)
        except Exception as e:
            # Если CQT упал — предупреждаем один раз и откатываемся к STFT
            if not self._warned_cqt:
                warnings.warn(f"librosa.cqt failed, falling back to stft: {e}")
                self._warned_cqt = True
            try:
                n_fft = max(32, min(len(analysis_data) // 2, 512))
                S = np.abs(librosa.stft(analysis_data, n_fft=n_fft, hop_length=max(16, n_fft // 4)))
                # Возьмём среднюю по частотам, затем ресайз в нужный размер
                freqs = librosa.fft_frequencies(sr=self.samplerate, n_fft=2048)
                # map freqs to log positions and then to bars
                cqt_frame = np.mean(S, axis=1)
            except Exception as e2:
                # полностью не получилось — возвращаем нули
                print(f"AudioProcessor fallback error: {e2}")
                cqt_frame = np.zeros(self.cqt_n_bins, dtype=float)

        # преобразуем мощность в dB-подобную меру (в пределах) — затем нормализуем и агрегируем в полосы
        # избегаем отрицательных/inf значений
        # добавляем eps для безопасности
        eps = 1e-10
        cqt_power = cqt_frame ** 2
        cqt_db = librosa.power_to_db(cqt_power, ref=np.max, top_db=80.0)
        # теперь нормируем 0..1 across this frame
        if np.isfinite(cqt_db).any():
            # shift to make min 0
            cmin = np.nanmin(cqt_db)
            cmax = np.nanmax(cqt_db)
            if cmax > cmin:
                normalized_bins = (cqt_db - cmin) / (cmax - cmin + eps)
            else:
                normalized_bins = np.zeros_like(cqt_db)
        else:
            normalized_bins = np.zeros_like(cqt_db)

        # агрегируем bins -> bar_count
        # равномерно разбиваем индексную ось cqt_bins -> баров (по порядку частот)
        # используем linear grouping — для CQT это примерно логарифмически-распределённые бины, но
        # мы просто суммируем соседние для получения нужного количества полос.
        total_bins = normalized_bins.shape[0]
        if total_bins < self.bar_count:
            # ападим нулями если мало
            padded = np.pad(normalized_bins, (0, self.bar_count - total_bins), mode="constant")
            grouped = padded[:self.bar_count]
        else:
            # делаем среднее по группам
            # вычисляем индексы границ
            idx = np.linspace(0, total_bins, num=self.bar_count + 1, dtype=int)
            grouped = np.zeros(self.bar_count, dtype=float)
            for i in range(self.bar_count):
                a, b = idx[i], idx[i+1]
                if b > a:
                    grouped[i] = np.mean(normalized_bins[a:b])
                else:
                    grouped[i] = 0.0

        # усиление пиков (контраст)
        boosted = np.power(grouped, self.peak_sharpness)
        new_data = np.sqrt(boosted)  # небольшая компрессия

        # применение режимов визуализации
        if self.visualization_mode == "bass_center":
            new_data = self._apply_bass_center(new_data)
        elif self.visualization_mode == "bass_edges":
            new_data = self._apply_bass_edges(new_data)

        # экспоненциальное сглаживание + ограничение скорости изменения
        with self._lock:
            smoothed = (1 - self.exp_smooth_factor) * self.fft_data + self.exp_smooth_factor * new_data
            delta = np.clip(smoothed - self.fft_data, -self.max_change_speed, self.max_change_speed)
            updated = self.fft_data + delta

            # скользящая усредняющая история
            self.fft_history.append(updated)
            averaged = np.mean(self.fft_history, axis=0)

            # адаптивная нормализация по истории максимумов (устойчивость к громкости)
            max_val = np.max(averaged) if np.max(averaged) > 0 else 0.0
            self.max_history.append(max_val + 1e-9)
            # используем 85-й перцентиль истории (устойчив к выбросам)
            historical_scale = np.percentile(self.max_history, 85) if len(self.max_history) > 0 else 1.0
            if historical_scale > 0.2:
                averaged = averaged / historical_scale

            # удаляем шумы
            averaged[averaged < self.noise_floor] = 0.0
            # окончательная клипировка
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
        # корректируем длину
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
