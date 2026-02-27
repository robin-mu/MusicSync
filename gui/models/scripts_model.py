from enum import IntEnum
from typing import Any

from PySide6.QtCore import QModelIndex
from PySide6 import QtCore, QtWidgets
from PySide6.QtWidgets import QCheckBox

from musicsync.music_sync_library import Script


class ScriptsTableColumn(IntEnum):
    ENABLED = 0
    NAME = 1
    TYPE = 2

    def __str__(self):
        if self == ScriptsTableColumn.NAME:
            return 'Name'
        if self == ScriptsTableColumn.ENABLED:
            return 'Enabled'
        if self == ScriptsTableColumn.TYPE:
            return 'Type'
        return None

    def status_tip(self):
        if self == ScriptsTableColumn.NAME:
            return 'The name of the field'
        if self == ScriptsTableColumn.ENABLED:
            return 'Whether this script will be executed for the current collection'
        if self == ScriptsTableColumn.TYPE:
            return 'The type of the script'
        return None


class ScriptsModel(QtCore.QAbstractTableModel):
    def __init__(self, scripts: list[Script]=None, parent=None):
        super(ScriptsModel, self).__init__(parent)

        self.parent = parent
        self.scripts = scripts or []
        self.sort_order = QtCore.Qt.SortOrder.AscendingOrder

    def rowCount(self, parent: QtCore.QModelIndex = QtCore.QModelIndex()):
        return len(self.scripts)

    def columnCount(self, parent: QtCore.QModelIndex = QtCore.QModelIndex()):
        return 2

    def data(self, index, /, role = QtCore.Qt.ItemDataRole.DisplayRole):
        if not index.isValid():
            return None

        data = ScriptsModel.field_to_row(self.scripts[index.row()])[index.column()]
        if role == QtCore.Qt.ItemDataRole.BackgroundRole:
            return data

        if role in [QtCore.Qt.ItemDataRole.DisplayRole, QtCore.Qt.ItemDataRole.EditRole] and index.column() == ScriptsTableColumn.NAME:
            return data

        return None

    def setData(self, index, value, /, role=QtCore.Qt.ItemDataRole.EditRole):
        if index.isValid():
            self.set_field_from_index(index, value)
            return True

        return False

    def flags(self, index):
        return QtCore.Qt.ItemFlag.ItemIsEditable | QtCore.Qt.ItemFlag.ItemIsEnabled | QtCore.Qt.ItemFlag.ItemIsSelectable

    def sort(self, column, /, order = None):
        if order is None:
            order = self.sort_order
        if column == ScriptsTableColumn.ENABLED:
            self.layoutAboutToBeChanged.emit()

            self.scripts = sorted(self.scripts, key=lambda field: field.name)
            self.scripts = sorted(self.scripts, key=lambda field: int(field.enabled), reverse=order == QtCore.Qt.SortOrder.DescendingOrder)

            self.layoutChanged.emit()
            self.sort_order = order

    @staticmethod
    def field_to_row(field: Script) -> tuple[bool, str]:
        return field.enabled, field.name

    def set_field_from_index(self, index: QModelIndex, value: Any):
        field = self.scripts[index.row()]
        column = index.column()
        if column == ScriptsTableColumn.ENABLED:
            field.enabled = value
        elif column == ScriptsTableColumn.NAME:
            field.name = value

    def update_checkboxes(self, enabled_fields: list[str]):
        for field in self.scripts:
            field.enabled = field.name in enabled_fields


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

    @staticmethod
    def _refresh(editor: QCheckBox, index):
        editor.blockSignals(True)
        editor.setChecked(index.model().data(index, role=QtCore.Qt.ItemDataRole.BackgroundRole))

        editor.blockSignals(False)

    def setModelData(self, editor: QCheckBox, model, index):
        model.setData(index, editor.isChecked())

    def refresh_editor(self, index: QtCore.QModelIndex = None):
        if index:
            self._refresh(self._editors.get(QtCore.QPersistentModelIndex(index)), index)
        else:
            for index, editor in self._editors.items():
                self._refresh(editor, index)
