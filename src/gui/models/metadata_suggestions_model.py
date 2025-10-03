from enum import IntEnum
from typing import Any
from xml.etree import ElementTree

from PySide6 import QtCore
from PySide6.QtCore import QModelIndex, QAbstractTableModel, QMimeData

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

        if role in [QtCore.Qt.ItemDataRole.DisplayRole, QtCore.Qt.ItemDataRole.EditRole, QtCore.Qt.ItemDataRole]:
            return MetadataSuggestionsModel.suggestion_to_row(self.suggestions[index.row()])[index.column()]
        else:
            return None

    def headerData(self, section, orientation, /, role=...):
        if role == QtCore.Qt.ItemDataRole.DisplayRole and orientation == QtCore.Qt.Orientation.Horizontal:
            return str(MetadataSuggestionsTableColumn(section))
        return None

    def setData(self, index, value, /, role=QtCore.Qt.ItemDataRole.EditRole):
        if role != QtCore.Qt.ItemDataRole.EditRole:
            return False
        if index.isValid():
            self.set_field_from_index(index, value)
            return True

        return False

    def flags(self, index):
        return (QtCore.Qt.ItemFlag.ItemIsEditable | QtCore.Qt.ItemFlag.ItemIsEnabled |
                QtCore.Qt.ItemFlag.ItemIsSelectable | QtCore.Qt.ItemFlag.ItemIsDragEnabled |
                QtCore.Qt.ItemFlag.ItemIsDropEnabled)

    def supportedDropActions(self):
        return QtCore.Qt.DropAction.MoveAction

    def mimeTypes(self, /):
        return ['application/xml']

    def mimeData(self, indexes):
        if not indexes:
            return None

        item = self.suggestions[indexes[0].row()]
        mime_data = QtCore.QMimeData()
        mime_data.setData('application/xml', ElementTree.tostring(item.to_xml()))
        return mime_data

    def dropMimeData(self, data, action, row, column, parent, /):
        if not data.hasFormat('application/xml'):
            return False

        dst_row = parent.row()
        if dst_row == -1:
            dst_row = self.rowCount()

        xml_data = ElementTree.fromstring(data.data('application/xml').data())
        item = MetadataSuggestion.from_xml(xml_data)

        src_row = self.parent.suggestions_table.selectedIndexes()[0].row()

        begin_dst = dst_row + int(dst_row > src_row)

        self.beginMoveRows(QtCore.QModelIndex(), src_row, src_row, QtCore.QModelIndex(), begin_dst)
        self.suggestions.pop(src_row)
        if dst_row > src_row:
            dst_row -= 1
        self.suggestions.insert(dst_row, item)
        self.endMoveRows()

        return True

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

    def relocateRow(self, from_index: int, to_index: int):
        row_last = max(from_index, to_index)
        row_first = min(from_index, to_index)

        #self.beginMoveRows(QtCore.QModelIndex(), row_last, row_last, QtCore.QModelIndex(), row_first)
        #self.suggestions.insert(to_index, self.suggestions.pop(from_index))
        #self.endMoveRows()