from PyQt5.QtCore import Qt, QRect, QTime
from PyQt5.QtGui import QColor, QFont

class ClockWidget:
    def __init__(self, config):
        self.config = config.get("clock", {})

    def paint(self, painter, size):
        if not self.config.get("enabled", True):
            return

        now = QTime.currentTime()
        hours = now.toString(self.config.get("format", {}).get("hours", "hh"))
        minutes = now.toString(self.config.get("format", {}).get("minutes", "mm"))

        font_size = int(size.height() * self.config.get("font_size_ratio", 0.2))
        font = QFont(self.config.get("font_family", "Helvetica"), font_size)

        weight = self.config.get("font_weight", "bold").lower()
        if weight == "bold":
            font.setWeight(QFont.Bold)
        elif weight == "light":
            font.setWeight(QFont.Light)
        else:
            font.setWeight(QFont.Normal)

        painter.setFont(font)

        color = QColor(self.config.get("color", "#FFFFFF"))
        color.setAlpha(self.config.get("opacity", 255))
        painter.setPen(color)

        fm = painter.fontMetrics()
        line_h = int(fm.height() * self.config.get("line_spacing", 1.0))
        offset_y = self.config.get("vertical_offset", 10)

        rect_h = QRect(0, offset_y, size.width(), line_h)
        rect_m = QRect(0, offset_y + line_h, size.width(), line_h)
        painter.drawText(rect_h, Qt.AlignHCenter, hours)
        painter.drawText(rect_m, Qt.AlignHCenter, minutes)
