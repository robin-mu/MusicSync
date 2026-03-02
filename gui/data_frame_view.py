from PySide6 import QtWidgets
from PySide6.QtCore import QModelIndex, QRect, Qt
from PySide6.QtGui import QPainter, QBrush, QColor


class DataFrameView(QtWidgets.QTableView):
    handle_size = 8

    def __init__(self, parent=None):
        super(DataFrameView, self).__init__(parent)
        self._fill_active = False
        self._fill_start_index = QModelIndex()
        self._fill_current_index = QModelIndex()

        self.setMouseTracking(True)

    def _fill_handle_rect(self, idx):
        visual_rect = self.visualRect(idx)
        s = self.handle_size
        return QRect(visual_rect.right() - s + 1, visual_rect.bottom() - s + 1, s, s)

    def paintEvent(self, event, /):
        super().paintEvent(event)

        idx = self.currentIndex()
        if not idx.isValid():
            return
        if not idx.column() in self.model().fillable_columns():
            return
        if not self.visualRect(idx).intersects(event.rect()):
            return

        painter = QPainter(self.viewport())
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, False)

        rect = self._fill_handle_rect(idx)
        painter.fillRect(rect, QColor(30, 30, 30))

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            idx = self.indexAt(event.pos())

            if idx.isValid() and idx.column() in self.model().fillable_columns() and self._fill_handle_rect(idx).contains(event.pos()):
                self._fill_active = True
                self._fill_start_index = idx
                self._fill_current_index = idx
                event.accept()
                return

        super().mousePressEvent(event)