from enum import IntEnum
from typing import Any

from PySide6.QtCore import QModelIndex
from PySide6 import QtCore, QtWidgets
from PySide6.QtWidgets import QCheckBox

from musicsync.music_sync_library import MetadataField


class MetadataFieldsTableColumn(IntEnum):
    ENABLED = 0
    NAME = 1
    TIMED_DATA = 2
    SHOW_FORMAT_OPTIONS = 3
    DEFAULT_FORMAT_AS_TITLE = 4
    DEFAULT_REMOVE_BRACKETS = 5

    def __str__(self):
        if self == MetadataFieldsTableColumn.NAME:
            return 'Name'
        if self == MetadataFieldsTableColumn.ENABLED:
            return 'Enabled'
        if self == MetadataFieldsTableColumn.TIMED_DATA:
            return 'Timed'
        if self == MetadataFieldsTableColumn.SHOW_FORMAT_OPTIONS:
            return 'Show format \noptions'
        if self == MetadataFieldsTableColumn.DEFAULT_FORMAT_AS_TITLE:
            return 'Default for format \noption "Format as title"'
        if self == MetadataFieldsTableColumn.DEFAULT_REMOVE_BRACKETS:
            return 'Default for format \noption "Remove brackets"'
        return None

    def status_tip(self):
        if self == MetadataFieldsTableColumn.NAME:
            return 'The name of the field'
        if self == MetadataFieldsTableColumn.ENABLED:
            return 'Whether suggestions for this field will be generated and shown'
        if self == MetadataFieldsTableColumn.TIMED_DATA:
            return 'Whether this field contains timed data in LRC format. These fields will have a special editor during metadata selection'
        if self == MetadataFieldsTableColumn.SHOW_FORMAT_OPTIONS:
            return 'Show buttons next to the suggestions to format the selected metadata'
        if self == MetadataFieldsTableColumn.DEFAULT_FORMAT_AS_TITLE:
            return 'Whether the format option "Format as title" will be enabled by default'
        if self == MetadataFieldsTableColumn.DEFAULT_REMOVE_BRACKETS:
            return 'Whether the format option "Remove brackets" will be enabled by default'
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
        return len(MetadataFieldsTableColumn.__members__)

    def data(self, index, /, role = QtCore.Qt.ItemDataRole.DisplayRole):
        if not index.isValid():
            return None

        data = MetadataFieldsModel.field_to_row(self.fields[index.row()])[index.column()]
        if role == QtCore.Qt.ItemDataRole.BackgroundRole:
            return data

        if role in [QtCore.Qt.ItemDataRole.DisplayRole, QtCore.Qt.ItemDataRole.EditRole] and index.column() == MetadataFieldsTableColumn.NAME:
            return data

        return None

    def headerData(self, section, orientation, /, role = ...):
        if role == QtCore.Qt.ItemDataRole.DisplayRole:
            return str(MetadataFieldsTableColumn(section))
        if role == QtCore.Qt.ItemDataRole.StatusTipRole:
            return MetadataFieldsTableColumn(section).status_tip()
        return None

    def setData(self, index, value, /, role=QtCore.Qt.ItemDataRole.EditRole):
        if index.isValid():
            self.set_field_from_index(index, value)
            if index.column() in [MetadataFieldsTableColumn.SHOW_FORMAT_OPTIONS, MetadataFieldsTableColumn.ENABLED]:
                self.parent.fields_table.itemDelegateForColumn(MetadataFieldsTableColumn.TIMED_DATA).refresh_editor()
                self.parent.fields_table.itemDelegateForColumn(MetadataFieldsTableColumn.SHOW_FORMAT_OPTIONS).refresh_editor()
                self.parent.fields_table.itemDelegateForColumn(MetadataFieldsTableColumn.DEFAULT_FORMAT_AS_TITLE).refresh_editor()
                self.parent.fields_table.itemDelegateForColumn(MetadataFieldsTableColumn.DEFAULT_REMOVE_BRACKETS).refresh_editor()
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

            self.parent.fields_table.itemDelegateForColumn(
                MetadataFieldsTableColumn.ENABLED).refresh_editor()
            self.parent.fields_table.itemDelegateForColumn(
                MetadataFieldsTableColumn.TIMED_DATA).refresh_editor()
            self.parent.fields_table.itemDelegateForColumn(
                MetadataFieldsTableColumn.SHOW_FORMAT_OPTIONS).refresh_editor()
            self.parent.fields_table.itemDelegateForColumn(
                MetadataFieldsTableColumn.DEFAULT_FORMAT_AS_TITLE).refresh_editor()
            self.parent.fields_table.itemDelegateForColumn(
                MetadataFieldsTableColumn.DEFAULT_REMOVE_BRACKETS).refresh_editor()

            self.layoutChanged.emit()
            self.sort_order = order

    @staticmethod
    def field_to_row(field: MetadataField) -> dict[int, Any]:
        return dict(zip(MetadataFieldsTableColumn.__members__.values(),
                        [field.enabled, field.name, field.timed_data, field.show_format_options,
                         field.default_format_as_title, field.default_remove_brackets]))

    def set_field_from_index(self, index: QModelIndex, value: Any):
        field = self.fields[index.row()]
        column = index.column()
        if column == MetadataFieldsTableColumn.ENABLED:
            field.enabled = value
        elif column == MetadataFieldsTableColumn.NAME:
            field.name = value
        elif column == MetadataFieldsTableColumn.TIMED_DATA:
            field.timed_data = value
        elif column == MetadataFieldsTableColumn.SHOW_FORMAT_OPTIONS:
            field.show_format_options = value
        elif column == MetadataFieldsTableColumn.DEFAULT_FORMAT_AS_TITLE:
            field.default_format_as_title = value
        elif column == MetadataFieldsTableColumn.DEFAULT_REMOVE_BRACKETS:
            field.default_remove_brackets = value

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

        enabled_index = index.model().index(index.row(), MetadataFieldsTableColumn.ENABLED)
        format_options_index = index.model().index(index.row(), MetadataFieldsTableColumn.SHOW_FORMAT_OPTIONS)
        enabled = index.model().data(enabled_index, role=QtCore.Qt.ItemDataRole.BackgroundRole)
        format_options = index.model().data(format_options_index, role=QtCore.Qt.ItemDataRole.BackgroundRole)

        if index.column() in [MetadataFieldsTableColumn.SHOW_FORMAT_OPTIONS, MetadataFieldsTableColumn.TIMED_DATA]:
            editor.setEnabled(enabled)
        elif index.column() >= MetadataFieldsTableColumn.DEFAULT_FORMAT_AS_TITLE:
            editor.setEnabled(enabled and format_options)

        editor.blockSignals(False)

    def setModelData(self, editor: QCheckBox, model, index):
        model.setData(index, editor.isChecked())

    def refresh_editor(self, index: QtCore.QModelIndex = None):
        if index:
            self._refresh(self._editors.get(QtCore.QPersistentModelIndex(index)), index)
        else:
            for index, editor in self._editors.items():
                self._refresh(editor, index)
