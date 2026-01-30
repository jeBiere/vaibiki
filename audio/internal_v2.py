from collections import deque
import numpy as np
import threading


class InternalAudioProcessorV2:
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
        accent_threshold: float = 1.8,
        accent_boost: float = 2.0,
        **_,
    ):
        self.bar_count = int(bar_count)
        self.samplerate = int(samplerate)
        self.blocksize = int(blocksize)
        self.buffer_blocks = int(max(1, buffer_blocks))
        self.exp_smooth_factor = float(exp_smooth_factor)
        self.max_change_speed = float(max_change_speed)
        self.noise_floor = float(noise_floor)
        self.peak_sharpness = float(peak_sharpness)
        self.avg_window_size = int(max(1, avg_window_size))
        self.visualization_mode = visualization_mode
        self.fmin = float(fmin)
        self.fmax = float(fmax)
        self.accent_threshold = float(accent_threshold)
        self.accent_boost = float(accent_boost)

        self.fft_data = np.zeros(self.bar_count, dtype=float)
        self.fft_history = deque(maxlen=self.avg_window_size)
        for _ in range(self.avg_window_size):
            self.fft_history.append(np.zeros(self.bar_count, dtype=float))

        self.energy_history = deque(maxlen=20)
        self.max_history = deque(maxlen=60)
        self.audio_buffer = np.zeros(0, dtype=float)
        self.buffer_size = self.blocksize * self.buffer_blocks

        self._lock = threading.Lock()

    def audio_callback(self, indata, frames, time, status):
        if indata.ndim == 1:
            audio_chunk = indata.astype(float)
        else:
            audio_chunk = np.mean(indata, axis=1).astype(float)

        current_energy = np.sqrt(np.mean(audio_chunk ** 2))
        self.energy_history.append(current_energy)
        avg_energy = np.mean(self.energy_history) if self.energy_history else 0.01
        is_accent = current_energy > avg_energy * self.accent_threshold

        self.audio_buffer = np.concatenate([self.audio_buffer, audio_chunk])
        if len(self.audio_buffer) > self.buffer_size:
            self.audio_buffer = self.audio_buffer[-self.buffer_size:]

        window = self.audio_buffer[-self.blocksize:]
        if len(window) < self.blocksize:
            window = np.pad(window, (0, self.blocksize - len(window)))

        window = window * np.hanning(len(window))
        spectrum = np.fft.rfft(window)
        magnitudes = np.abs(spectrum)

        freqs = np.fft.rfftfreq(len(window), 1.0 / self.samplerate)
        mask = (freqs >= self.fmin) & (freqs <= self.fmax)
        freqs = freqs[mask]
        magnitudes = magnitudes[mask]
        if freqs.size == 0:
            return

        magnitudes = np.log1p(magnitudes)
        bins = np.interp(
            np.linspace(freqs.min(), freqs.max(), self.bar_count),
            freqs,
            magnitudes,
        )

        if is_accent:
            bins *= self.accent_boost

        bins = np.power(bins, self.peak_sharpness)
        if np.max(bins) > 0:
            bins = bins / (np.max(bins) + 1e-9)

        bins[bins < self.noise_floor] = 0.0

        if self.visualization_mode == "bass_center":
            bins = self._apply_bass_center(bins)
        elif self.visualization_mode == "bass_edges":
            bins = self._apply_bass_edges(bins)

        with self._lock:
            smoothed = (1 - self.exp_smooth_factor) * self.fft_data + self.exp_smooth_factor * bins
            delta = np.clip(smoothed - self.fft_data, -self.max_change_speed, self.max_change_speed)
            updated = self.fft_data + delta

            self.fft_history.append(updated)
            averaged = np.mean(self.fft_history, axis=0)

            max_val = np.max(averaged) if np.max(averaged) > 0 else 0.0
            self.max_history.append(max_val + 1e-9)
            scale = np.percentile(self.max_history, 85) if self.max_history else 1.0
            if scale > 0:
                averaged = averaged / scale

            averaged[averaged < self.noise_floor] = 0.0
            self.fft_data = np.clip(averaged, 0.0, 1.0)

    def _apply_bass_center(self, data: np.ndarray) -> np.ndarray:
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
        bass_count = max(4, self.bar_count // 12)
        center_count = self.bar_count - bass_count * 2
        bass_data = data[:bass_count]
        center_data = data[bass_count: bass_count + center_count]
        right_bass = bass_data[::-1]
        result = np.concatenate([bass_data, center_data, right_bass])
        if result.size < self.bar_count:
            result = np.pad(result, (0, self.bar_count - result.size), mode="constant")
        return result[:self.bar_count]

    def get_fft_data(self):
        with self._lock:
            return self.fft_data.copy()
