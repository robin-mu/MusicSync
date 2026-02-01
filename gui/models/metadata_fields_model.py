from enum import IntEnum
from typing import Any

from PySide6.QtCore import QModelIndex
from PySide6 import QtCore, QtWidgets
from PySide6.QtWidgets import QCheckBox

from musicsync.music_sync_library import MetadataField


class MetadataFieldsTableColumn(IntEnum):
    ENABLED = 0
    NAME = 1

    def __str__(self):
        if self == MetadataFieldsTableColumn.NAME:
            return 'Name'
        if self == MetadataFieldsTableColumn.ENABLED:
            return 'Enabled'
        return None

    def status_tip(self):
        if self == MetadataFieldsTableColumn.NAME:
            return 'The name of the field'
        if self == MetadataFieldsTableColumn.ENABLED:
            return 'Whether suggestions for this field will be generated and shown'
        return None


class MetadataFieldsModel(QtCore.QAbstractTableModel):
    def __init__(self, fields: list[MetadataField]=None, parent=None):
        super(MetadataFieldsModel, self).__init__(parent)

        self.parent = parent
        self.fields = fields or []
        self.sort_order = QtCore.Qt.SortOrder.AscendingOrder

    def rowCount(self, parent: QtCore.QModelIndex = QtCore.QModelIndex()):
        return len(self.fields)

    def columnCount(self, parent: QtCore.QModelIndex = QtCore.QModelIndex()):
        return 2

    def data(self, index, /, role = QtCore.Qt.ItemDataRole.DisplayRole):
        if not index.isValid():
            return None

        data = MetadataFieldsModel.field_to_row(self.fields[index.row()])[index.column()]
        if role == QtCore.Qt.ItemDataRole.BackgroundRole:
            return data

        if role in [QtCore.Qt.ItemDataRole.DisplayRole, QtCore.Qt.ItemDataRole.EditRole] and index.column() == MetadataFieldsTableColumn.NAME:
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
        if column == MetadataFieldsTableColumn.ENABLED:
            self.layoutAboutToBeChanged.emit()

            self.fields = sorted(self.fields, key=lambda field: field.name)
            self.fields = sorted(self.fields, key=lambda field: int(field.enabled), reverse=order == QtCore.Qt.SortOrder.DescendingOrder)

            self.layoutChanged.emit()
            self.sort_order = order

    @staticmethod
    def field_to_row(field: MetadataField) -> tuple[bool, str]:
        return field.enabled, field.name

    def set_field_from_index(self, index: QModelIndex, value: Any):
        field = self.fields[index.row()]
        column = index.column()
        if column == MetadataFieldsTableColumn.ENABLED:
            field.enabled = value
        elif column == MetadataFieldsTableColumn.NAME:
            field.name = value

    def update_checkboxes(self, enabled_fields: list[str]):
        for field in self.fields:
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
