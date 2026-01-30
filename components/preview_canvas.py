from PyQt5.QtCore import Qt, QRectF, QSize, pyqtSignal
from PyQt5.QtGui import QPainter, QPen, QColor
from PyQt5.QtWidgets import QWidget

from components.visualization import Visualization
from components.clock import ClockWidget
from components.overlay import Overlay


class PreviewCanvas(QWidget):
    visualizer_rect_changed = pyqtSignal(int, int, int, int)

    def __init__(self, config, screen_size):
        super().__init__()
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.config = config
        self.screen_size = screen_size
        self._drag_mode = None
        self._drag_start = None
        self._start_rect = None
        self._handle_size = 10
        self._init_components()

    def _init_components(self):
        self.visualization = Visualization(self.config)
        self.clock = ClockWidget(self.config)
        self.overlay = None
        if self.config.get("overlay", {}).get("enabled", True):
            self.overlay = Overlay(self.config, QSize(
                self.config["visualizer"]["width"],
                self.config["visualizer"]["height"],
            ))

    def set_config(self, config):
        self.config = config
        self._init_components()
        self.update()

    def set_fft_data(self, data):
        self.visualization.fft_data = data

    def set_screen_size(self, screen_size):
        self.screen_size = screen_size
        self.update()

    def _screen_rect(self):
        if self.screen_size.width() <= 0 or self.screen_size.height() <= 0:
            return QRectF(0, 0, self.width(), self.height())
        padding = 12
        target_ratio = self.screen_size.width() / self.screen_size.height()
        avail_w = max(1, self.width() - padding * 2)
        avail_h = max(1, self.height() - padding * 2)
        if avail_w / avail_h > target_ratio:
            height = avail_h
            width = height * target_ratio
        else:
            width = avail_w
            height = width / target_ratio
        x = (self.width() - width) / 2
        y = (self.height() - height) / 2
        return QRectF(x, y, width, height)

    def _to_screen_coords(self, x, y):
        screen_rect = self._screen_rect()
        sx = screen_rect.x() + x / self.screen_size.width() * screen_rect.width()
        sy = screen_rect.y() + y / self.screen_size.height() * screen_rect.height()
        return sx, sy

    def _from_screen_coords(self, sx, sy):
        screen_rect = self._screen_rect()
        x = (sx - screen_rect.x()) / screen_rect.width() * self.screen_size.width()
        y = (sy - screen_rect.y()) / screen_rect.height() * self.screen_size.height()
        return x, y

    def _visualizer_rect(self):
        vis = self.config["visualizer"]
        screen_rect = self._screen_rect()
        x = screen_rect.x() + vis["x"] / self.screen_size.width() * screen_rect.width()
        y = screen_rect.y() + vis["y"] / self.screen_size.height() * screen_rect.height()
        w = vis["width"] / self.screen_size.width() * screen_rect.width()
        h = vis["height"] / self.screen_size.height() * screen_rect.height()
        return QRectF(x, y, w, h)

    def _handles(self, rect):
        hs = self._handle_size
        return {
            "tl": QRectF(rect.left() - hs / 2, rect.top() - hs / 2, hs, hs),
            "tr": QRectF(rect.right() - hs / 2, rect.top() - hs / 2, hs, hs),
            "bl": QRectF(rect.left() - hs / 2, rect.bottom() - hs / 2, hs, hs),
            "br": QRectF(rect.right() - hs / 2, rect.bottom() - hs / 2, hs, hs),
        }

    def _hit_test(self, pos, rect):
        for name, handle in self._handles(rect).items():
            if handle.contains(pos):
                return name
        if rect.contains(pos):
            return "move"
        return None

    def mousePressEvent(self, event):
        rect = self._visualizer_rect()
        hit = self._hit_test(event.pos(), rect)
        if hit:
            self._drag_mode = hit
            self._drag_start = event.pos()
            self._start_rect = QRectF(rect)
        else:
            self._drag_mode = None
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if not self._drag_mode:
            super().mouseMoveEvent(event)
            return

        dx = event.pos().x() - self._drag_start.x()
        dy = event.pos().y() - self._drag_start.y()
        rect = QRectF(self._start_rect)

        if self._drag_mode == "move":
            rect.translate(dx, dy)
        else:
            if "l" in self._drag_mode:
                rect.setLeft(rect.left() + dx)
            if "r" in self._drag_mode:
                rect.setRight(rect.right() + dx)
            if "t" in self._drag_mode:
                rect.setTop(rect.top() + dy)
            if "b" in self._drag_mode:
                rect.setBottom(rect.bottom() + dy)

        rect = self._clamp_rect(rect)
        self._emit_rect(rect)
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        self._drag_mode = None
        super().mouseReleaseEvent(event)

    def _clamp_rect(self, rect):
        screen_rect = self._screen_rect()
        min_w = 50
        min_h = 30
        if rect.width() < min_w:
            rect.setWidth(min_w)
        if rect.height() < min_h:
            rect.setHeight(min_h)
        if rect.left() < screen_rect.left():
            rect.moveLeft(screen_rect.left())
        if rect.top() < screen_rect.top():
            rect.moveTop(screen_rect.top())
        if rect.right() > screen_rect.right():
            rect.moveRight(screen_rect.right())
        if rect.bottom() > screen_rect.bottom():
            rect.moveBottom(screen_rect.bottom())
        snap = 8
        if abs(rect.left() - screen_rect.left()) < snap:
            rect.moveLeft(screen_rect.left())
        if abs(rect.top() - screen_rect.top()) < snap:
            rect.moveTop(screen_rect.top())
        if abs(rect.right() - screen_rect.right()) < snap:
            rect.moveRight(screen_rect.right())
        if abs(rect.bottom() - screen_rect.bottom()) < snap:
            rect.moveBottom(screen_rect.bottom())
        return rect

    def _emit_rect(self, rect):
        screen_rect = self._screen_rect()
        x = (rect.x() - screen_rect.x()) / screen_rect.width() * self.screen_size.width()
        y = (rect.y() - screen_rect.y()) / screen_rect.height() * self.screen_size.height()
        w = rect.width() / screen_rect.width() * self.screen_size.width()
        h = rect.height() / screen_rect.height() * self.screen_size.height()
        self.visualizer_rect_changed.emit(int(x), int(y), int(w), int(h))

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        screen_rect = self._screen_rect()
        painter.setPen(QPen(QColor("#2a2a2a"), 1))
        painter.setBrush(QColor("#141414"))
        painter.drawRoundedRect(screen_rect, 8, 8)
        painter.setPen(QPen(QColor("#1f2a33"), 1))
        painter.drawLine(
            screen_rect.center().x(),
            screen_rect.top(),
            screen_rect.center().x(),
            screen_rect.bottom(),
        )
        painter.drawLine(
            screen_rect.left(),
            screen_rect.center().y(),
            screen_rect.right(),
            screen_rect.center().y(),
        )

        rect = self._visualizer_rect()
        painter.save()
        painter.setClipRect(rect)
        painter.translate(rect.topLeft())

        size = QSize(int(rect.width()), int(rect.height()))
        self.visualization.paint(painter, size)
        self.clock.paint(painter, size)
        if self.overlay is not None:
            self.overlay.paint(painter, size)
        painter.restore()

        painter.setPen(QPen(QColor("#4da3ff"), 2))
        painter.setBrush(Qt.NoBrush)
        painter.drawRect(rect)

        painter.setBrush(QColor("#4da3ff"))
        for handle in self._handles(rect).values():
            painter.drawRect(handle)

        vis = self.config["visualizer"]
        label = f"{vis['x']},{vis['y']} {vis['width']}x{vis['height']}"
        painter.setPen(QPen(QColor("#8fbfff"), 1))
        painter.drawText(rect.adjusted(6, -18, 0, 0), label)
