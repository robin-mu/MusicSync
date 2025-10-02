from enum import IntEnum

from PySide6 import QtCore, QtWidgets
from PySide6.QtWidgets import QCheckBox

from src.music_sync_library import MetadataField


class MetadataFieldsTableColumns(IntEnum):
    NAME = 0
    SHOW_FORMAT_OPTIONS = 1
    DEFAULT_FORMAT_AS_TITLE = 2
    DEFAULT_REMOVE_BRACKETS = 3


class MetadataFieldsModel(QtCore.QAbstractTableModel):
    def __init__(self, fields: list[MetadataField], parent: 'MetadataSuggestionsDialog'=None):
        super(MetadataFieldsModel, self).__init__(parent)

        self.parent = parent
        self.fields = fields

    def rowCount(self, parent: QtCore.QModelIndex = QtCore.QModelIndex()):
        return len(self.fields)

    def columnCount(self, parent: QtCore.QModelIndex = QtCore.QModelIndex()):
        return len(MetadataFieldsTableColumns.__members__)

    def data(self, index, /, role = QtCore.Qt.ItemDataRole.DisplayRole):
        if not index.isValid():
            return None

        data = self.fields[index.row()].to_row()[index.column()]
        if role == QtCore.Qt.ItemDataRole.BackgroundRole:
            return data

        if role == QtCore.Qt.ItemDataRole.DisplayRole and index.column() == MetadataFieldsTableColumns.NAME:
            return data

        return None

    def headerData(self, section, orientation, /, role = ...):
        if role == QtCore.Qt.ItemDataRole.DisplayRole and orientation == QtCore.Qt.Orientation.Horizontal:
            if section == MetadataFieldsTableColumns.NAME:
                return 'Name'
            if section == MetadataFieldsTableColumns.SHOW_FORMAT_OPTIONS:
                return 'Show format \noptions'
            if section == MetadataFieldsTableColumns.DEFAULT_FORMAT_AS_TITLE:
                return 'Default for format \noption "Format as title"'
            if section == MetadataFieldsTableColumns.DEFAULT_REMOVE_BRACKETS:
                return 'Default for format \noption "Remove brackets"'
        return None

    def setData(self, index, value, /, role=QtCore.Qt.ItemDataRole.EditRole):
        if index.isValid():
            self.fields[index.row()].set_from_column(index.column(), value)
            if index.column() == MetadataFieldsTableColumns.SHOW_FORMAT_OPTIONS:
                self.parent.columns_table.itemDelegateForColumn(2).refresh_editor()
                self.parent.columns_table.itemDelegateForColumn(3).refresh_editor()
            return True

        return False

    def flags(self, index):
        return QtCore.Qt.ItemFlag.ItemIsEditable | QtCore.Qt.ItemFlag.ItemIsEnabled


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
        if index.column() >= MetadataFieldsTableColumns.DEFAULT_FORMAT_AS_TITLE:
            format_options_index = index.model().index(index.row(), MetadataFieldsTableColumns.SHOW_FORMAT_OPTIONS)
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
