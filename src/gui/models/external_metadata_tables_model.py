from enum import IntEnum
from typing import Any

from PySide6 import QtCore
from PySide6.QtCore import QModelIndex

from src.gui.models.metadata_fields_model import MetadataFieldsTableColumn
from src.music_sync_library import ExternalMetadataTable


class ExternalMetadataTablesColumn(IntEnum):
    ID = 0
    NAME = 1
    PATH = 2

    def __str__(self):
        if self == ExternalMetadataTablesColumn.ID:
            return 'ID'
        if self == ExternalMetadataTablesColumn.NAME:
            return 'Name'
        if self == ExternalMetadataTablesColumn.PATH:
            return 'Path'
        return None

    def tool_tip(self):
        if self == ExternalMetadataTablesColumn.ID:
            return 'The ID is used to reference a table in suggestion generation. Use the syntax [id]_[field] to refer to a field of a table.'
        return None



class ExternalMetadataTablesModel(QtCore.QAbstractTableModel):
    def __init__(self, tables: list[ExternalMetadataTable], parent: 'MetadataSuggestionsDialog'=None):
        super(ExternalMetadataTablesModel, self).__init__(parent)

        self.parent = parent
        self.tables = tables

    def rowCount(self, parent: QtCore.QModelIndex = QtCore.QModelIndex()):
        return len(self.tables)

    def columnCount(self, parent: QtCore.QModelIndex = QtCore.QModelIndex()):
        return len(ExternalMetadataTablesColumn.__members__)

    def data(self, index, /, role = QtCore.Qt.ItemDataRole.DisplayRole):
        if not index.isValid():
            return None

        if role in [QtCore.Qt.ItemDataRole.DisplayRole, QtCore.Qt.ItemDataRole.EditRole]:
            return ExternalMetadataTablesModel.field_to_row(self.tables[index.row()])[index.column()]

        return None

    def headerData(self, section, orientation, /, role = ...):
        if role == QtCore.Qt.ItemDataRole.DisplayRole:
            return str(ExternalMetadataTablesColumn(section))
        if role == QtCore.Qt.ItemDataRole.ToolTipRole:
            return ExternalMetadataTablesColumn(section).tool_tip()
        return None

    def setData(self, index, value, /, role=QtCore.Qt.ItemDataRole.EditRole):
        if index.isValid():
            self.set_field_from_index(index, value)
            return True

        return False

    def flags(self, index):
        flags = QtCore.Qt.ItemFlag.ItemIsEnabled | QtCore.Qt.ItemFlag.ItemIsSelectable
        if index.column() != ExternalMetadataTablesColumn.ID and index.row() != 0:
            flags |= QtCore.Qt.ItemFlag.ItemIsEditable
        return flags

    @staticmethod
    def field_to_row(table: ExternalMetadataTable) -> dict[int, Any]:
        return dict(zip(MetadataFieldsTableColumn.__members__.values(), [table.id, table.name, table.path]))

    def set_field_from_index(self, index: QModelIndex, value: Any):
        table = self.tables[index.row()]
        column = index.column()
        if column == ExternalMetadataTablesColumn.ID:
            table.id = value
        elif column == ExternalMetadataTablesColumn.NAME:
            table.name = value
        elif column == ExternalMetadataTablesColumn.PATH:
            table.path = value
