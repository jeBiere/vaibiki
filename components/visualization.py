from PyQt5.QtGui import QLinearGradient, QColor
from PyQt5.QtCore import Qt

class Visualization:
    def __init__(self, config):
        vis_conf = config["visualizer"]

        self.bar_count = config["bar_count"]
        self.gradient_start = QColor(vis_conf["gradient_start"])
        self.gradient_end = QColor(vis_conf["gradient_end"])
        self.shift_y = vis_conf["shift_y"]

        self.fft_data = [0] * self.bar_count

    def paint(self, painter, size):
        width = size.width()
        height = size.height()
        available_height = height - self.shift_y
        max_bar_height = available_height
        bar_width = width // self.bar_count
        left_offset = 0

        for i, val in enumerate(self.fft_data):
            raw_height = val * available_height
            bar_height = int(min(raw_height, max_bar_height))
            x = left_offset + i * bar_width
            y = height - bar_height - self.shift_y

            gradient = QLinearGradient(x, y, x, y + bar_height)
            gradient.setColorAt(0, self.gradient_start)
            gradient.setColorAt(1, self.gradient_end)

            painter.setBrush(gradient)
            painter.setPen(Qt.NoPen)
            painter.drawRoundedRect(x, y, bar_width - 2, bar_height, 6, 6)
