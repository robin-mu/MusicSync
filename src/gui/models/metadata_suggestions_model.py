from enum import IntEnum
from typing import Any

from PySide6 import QtCore
from PySide6.QtCore import QModelIndex, QAbstractTableModel

from src.music_sync_library import MetadataSuggestion


class MetadataSuggestionsTableColumn(IntEnum):
    FROM = 0
    TO = 1
    SPLIT = 2
    SLICE = 3

    def __str__(self):
        if self == MetadataSuggestionsTableColumn.FROM:
            return 'From'
        if self == MetadataSuggestionsTableColumn.TO:
            return 'To'
        if self == MetadataSuggestionsTableColumn.SPLIT:
            return 'Split at'
        if self == MetadataSuggestionsTableColumn.SLICE:
            return 'Index/Slice'
        return None

class MetadataSuggestionsModel(QAbstractTableModel):
    def __init__(self, suggestions: list[MetadataSuggestion], parent: 'MetadataSuggestionsDialog' = None):
        super(MetadataSuggestionsModel, self).__init__()

        self.parent = parent
        self.suggestions = suggestions

    def rowCount(self, parent: QtCore.QModelIndex = QtCore.QModelIndex()):
        return len(self.suggestions)

    def columnCount(self, parent: QtCore.QModelIndex = QtCore.QModelIndex()):
        return len(MetadataSuggestionsTableColumn.__members__)

    def data(self, index, /, role=QtCore.Qt.ItemDataRole.DisplayRole):
        if not index.isValid():
            return None

        if role in [QtCore.Qt.ItemDataRole.DisplayRole, QtCore.Qt.ItemDataRole.EditRole]:
            return MetadataSuggestionsModel.suggestion_to_row(self.suggestions[index.row()])[index.column()]
        else:
            return None

    def headerData(self, section, orientation, /, role=...):
        if role == QtCore.Qt.ItemDataRole.DisplayRole and orientation == QtCore.Qt.Orientation.Horizontal:
            return str(MetadataSuggestionsTableColumn(section))
        return None

    def setData(self, index, value, /, role=QtCore.Qt.ItemDataRole.EditRole):
        print(index.row(), index.column(), value, role)
        if index.isValid():
            self.set_field_from_index(index, value)
            return True

        return False

    def flags(self, index):
        return QtCore.Qt.ItemFlag.ItemIsEditable | QtCore.Qt.ItemFlag.ItemIsEnabled | QtCore.Qt.ItemFlag.ItemIsSelectable

    @staticmethod
    def suggestion_to_row(suggestion: MetadataSuggestion) -> dict[int, Any]:
        return {
            MetadataSuggestionsTableColumn.FROM: suggestion.pattern_from,
            MetadataSuggestionsTableColumn.TO: suggestion.pattern_to,
            MetadataSuggestionsTableColumn.SPLIT: suggestion.split_separators,
            MetadataSuggestionsTableColumn.SLICE: suggestion.split_slice
        }

    def set_field_from_index(self, index: QModelIndex, value: Any):
        suggestion = self.suggestions[index.row()]
        column = index.column()
        if column == MetadataSuggestionsTableColumn.FROM:
            suggestion.pattern_from = value
        elif column == MetadataSuggestionsTableColumn.TO:
            suggestion.pattern_to = value
        elif column == MetadataSuggestionsTableColumn.SPLIT:
            suggestion.split_separators = value
        elif column == MetadataSuggestionsTableColumn.SLICE:
            suggestion.split_slice = value