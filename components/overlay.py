import os
from PyQt5.QtGui import QPixmap
from PyQt5.QtCore import Qt

class Overlay:
    def __init__(self, config, size):
        overlay_config = config.get("overlay", {})
        overlay_path = overlay_config.get("image", "")
        scale_mode = overlay_config.get("scale_mode", "fill")

        base_dir = os.path.dirname(os.path.abspath(__file__))
        project_root = os.path.normpath(os.path.join(base_dir, ".."))

        full_path = os.path.join(project_root, overlay_path)
        full_path = os.path.normpath(full_path)

        self.pixmap = QPixmap(full_path)

        if self.pixmap.isNull():
            print(f"Warning: Overlay image '{full_path}' not found or invalid")
            self.pixmap = QPixmap()
        else:
            if scale_mode == "fit":
                mode = Qt.KeepAspectRatio
            elif scale_mode == "stretch":
                mode = Qt.IgnoreAspectRatio
            else:
                mode = Qt.KeepAspectRatioByExpanding
            self.pixmap = self.pixmap.scaled(size, mode, Qt.SmoothTransformation)

    def paint(self, painter, size):
        if not self.pixmap.isNull():
            painter.drawPixmap(0, 0, self.pixmap)
