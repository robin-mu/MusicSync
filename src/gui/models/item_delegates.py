from typing import Any

from PySide6 import QtWidgets, QtCore
from PySide6.QtCore import QEvent
from PySide6.QtWidgets import QComboBox


class ComboBoxDelegate(QtWidgets.QStyledItemDelegate):
    def __init__(self, editable: bool=False, update_callback=None, parent=None):
        super(ComboBoxDelegate, self).__init__(parent)
        self._editors = {}
        self.editable = editable
        self.update_callback = update_callback
        self.parent = parent

        self.installEventFilter(self)

    def to_model_data(self, val: str) -> Any:
        return val

    def get_combobox_items(self, index) -> list[str]:
        return [index.model().data(index, role=QtCore.Qt.ItemDataRole.BackgroundRole)]

    def get_combobox_selection(self, index) -> str:
        return index.model().data(index, role=QtCore.Qt.ItemDataRole.BackgroundRole)

    def get_status_bar_text(self, index, box: QComboBox) -> str:
        return str(index)

    def createEditor(self, parent, option, index):
        combo = QtWidgets.QComboBox(parent)
        combo.setEditable(self.editable)

        if self.update_callback is not None:
            combo.currentTextChanged.connect(self.update_callback)

        pindex = QtCore.QPersistentModelIndex(index)
        self._editors[pindex] = combo
        combo.destroyed.connect(lambda obj, pidx=pindex: self._editors.pop(pidx, None))
        combo.highlighted[int].connect(lambda index, box=combo: self.parent.statusbar.showMessage(self.get_status_bar_text(index, box)))
        return combo

    def setEditorData(self, editor: QComboBox, index):
        editor.blockSignals(True)
        editor.clear()
        editor.addItems(self.get_combobox_items(index))
        editor.setCurrentText(self.get_combobox_selection(index))
        editor.blockSignals(False)

    def setModelData(self, editor: QComboBox, model, index):
        model.setData(index, self.to_model_data(editor.currentText()))

    def eventFilter(self, obj, event):
        if event.type() != QEvent.Type.Paint:
            print(QEvent.Type(event.type()).name)
        if event.type() in (QEvent.Type.HoverMove, QEvent.Type.HoverEnter, QEvent.Type.MouseButtonPress):
            self.parent.statusbar.showMessage(self.get_status_bar_text(obj.currentIndex(), obj))
        if event.type() in (QEvent.Type.Hide, QEvent.Type.FocusIn, QEvent.Type.HoverLeave):
            self.parent.statusbar.clearMessage()
        return super(ComboBoxDelegate, self).eventFilter(obj, event)