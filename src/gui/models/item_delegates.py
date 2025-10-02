from PyQt6.QtWidgets import QCheckBox
from PySide6 import QtWidgets, QtCore


class CheckboxDelegate(QtWidgets.QStyledItemDelegate):
    def __init__(self, parent=None):
        super(CheckboxDelegate, self).__init__(parent)
        self._editors = {}

    def createEditor(self, parent, option, index):
        checkbox = QtWidgets.QCheckBox(parent)
        checkbox.toggled.connect(lambda val: index.model().setData(index, val))

        pindex = QtCore.QPersistentModelIndex(index)
        self._editors[pindex] = checkbox
        checkbox.destroyed.connect(lambda obj, pidx=pindex: self._editors.pop(pidx, None))
        return checkbox

    def setEditorData(self, editor: QCheckBox, index):
        self._refresh(editor, index)

    def _refresh(self, editor: QCheckBox, index):
        editor.blockSignals(True)
        editor.setChecked(index.model().data(index, role=QtCore.Qt.ItemDataRole.BackgroundRole))
        if index.column() > 1:
            format_options_index = index.model().index(index.row(), 1)
            editor.setEnabled(index.model().data(format_options_index, role=QtCore.Qt.ItemDataRole.BackgroundRole))
        editor.blockSignals(False)

    def setModelData(self, editor: QCheckBox, model, index):
        model.setData(index, editor.isChecked())

    def refresh_editor(self, index: QtCore.QModelIndex = None):
        if index:
            self._refresh(self._editors.get(QtCore.QPersistentModelIndex(index)), index)
        else:
            for index, editor in self._editors.items():
                self._refresh(editor, index)
