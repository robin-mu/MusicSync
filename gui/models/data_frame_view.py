from PySide6 import QtWidgets, QtCore
from PySide6.QtCore import QModelIndex, QRect, Qt, QPoint
from PySide6.QtGui import QPainter, QColor, QPen

from gui.models.item_delegates import ComboBoxDelegate


class DataFrameView(QtWidgets.QTableView):
    handle_size = 8

    def __init__(self, parent=None):
        super(DataFrameView, self).__init__(parent)
        self._fill_active = False
        self._fill_start_index = QModelIndex()
        self._fill_start_position = QPoint(0, 0)
        self._fill_current_index = QModelIndex()

        self.setMouseTracking(True)
        self.viewport().setMouseTracking(True)

    def _fill_handle_rect(self, idx):
        visual_rect = self.visualRect(idx)
        s = self.handle_size
        return QRect(visual_rect.right() - s + 1, visual_rect.bottom() - s + 1, s, s)

    def paintEvent(self, event, /):
        super().paintEvent(event)

        if self.model() is None:
            return

        painter = QPainter(self.viewport())
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, False)

        # fill handle
        top_idx = self.indexAt(QPoint(0, 0))
        bottom_idx = self.indexAt(QPoint(0, self.viewport().height() - 1))
        if not bottom_idx.isValid():
            bottom_idx = self.model().index(self.model().rowCount() - 1, 0)

        for col in self.model().fillable_columns():
            for row in range(top_idx.row(), bottom_idx.row() + 1):
                idx = self.model().index(row, col)
                rect = self._fill_handle_rect(idx)
                painter.fillRect(rect, QColor(0, 0, 0))

        # fill outline
        if self._fill_active:
            visual_rect_start = self.visualRect(self._fill_start_index)
            visual_rect_end = self.visualRect(self._fill_current_index)

            rect = visual_rect_start.united(visual_rect_end)
            rect.adjust(0, 0, -1, -1)
            pen = QPen(QColor(200, 200, 200), 2, QtCore.Qt.PenStyle.SolidLine)
            painter.setPen(pen)
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawRect(rect)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            idx = self.indexAt(event.pos())

            if idx.isValid() and idx.column() in self.model().fillable_columns() and self._fill_handle_rect(idx).contains(event.pos()):
                self._fill_active = True
                self._fill_start_index = idx
                self._fill_start_position = event.pos()
                self._fill_current_index = idx
                event.accept()
                return

        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self._fill_active:
            idx = self.indexAt(QPoint(self._fill_start_position.x(), event.pos().y()))
            if idx.isValid():
                self._fill_current_index = self.model().index(idx.row(), self._fill_start_index.column())

            self.viewport().update()
            event.accept()
            return

        idx = self.indexAt(event.pos())
        if idx.isValid() and idx.column() in self.model().fillable_columns() and self._fill_handle_rect(idx).contains(event.pos()):
            if self.viewport().cursor().shape() != Qt.CursorShape.CrossCursor:
                self.viewport().setCursor(Qt.CursorShape.CrossCursor)
        else:
            if self.viewport().cursor().shape() != Qt.CursorShape.ArrowCursor:
                self.viewport().setCursor(Qt.CursorShape.ArrowCursor)

        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if self._fill_active and event.button() == Qt.MouseButton.LeftButton:
            self._apply_fill()

            self.viewport().update()
            idx = self.indexAt(event.pos())
            if not (idx.isValid() and idx.column() in self.model().fillable_columns() and self._fill_handle_rect(
                    idx).contains(event.pos())):
                self.viewport().setCursor(Qt.CursorShape.ArrowCursor)
            event.accept()
            self._fill_active = False
            return
        super().mouseReleaseEvent(event)

    def _apply_fill(self):
        model = self.model()
        col = self._fill_start_index.column()
        row_start, row_end = sorted([self._fill_start_index.row(), self._fill_current_index.row()])

        src = model.data(self._fill_start_index, Qt.ItemDataRole.BackgroundRole)

        model.layoutAboutToBeChanged.emit()
        for row in range(row_start, row_end + 1):
            if row == self._fill_start_index.row():
                continue

            idx = model.index(row, col)
            if not (model.flags(idx) & Qt.ItemFlag.ItemIsEditable):
                continue

            if isinstance(self.itemDelegateForColumn(col), ComboBoxDelegate) and src.gui_string not in self.itemDelegateForColumn(col).get_combobox_items(idx):
                continue

            model.setData(idx, src, Qt.ItemDataRole.EditRole)
        model.layoutChanged.emit()