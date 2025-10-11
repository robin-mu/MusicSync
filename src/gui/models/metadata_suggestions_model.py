from enum import IntEnum
from typing import Any
from xml.etree import ElementTree

from PySide6 import QtCore
from PySide6.QtCore import QAbstractTableModel, QModelIndex

from src.music_sync_library import MetadataSuggestion


class MetadataSuggestionsTableColumn(IntEnum):
    FROM = 0
    TO = 1
    REPLACE_REGEX = 2
    REPLACE_WITH = 3
    SPLIT = 4
    SLICE = 5

    def __str__(self):
        if self == MetadataSuggestionsTableColumn.FROM:
            return 'Format'
        if self == MetadataSuggestionsTableColumn.TO:
            return 'Filter'
        if self == MetadataSuggestionsTableColumn.REPLACE_REGEX:
            return 'Replace'
        if self == MetadataSuggestionsTableColumn.REPLACE_WITH:
            return 'Replace with'
        if self == MetadataSuggestionsTableColumn.SPLIT:
            return 'Split at'
        if self == MetadataSuggestionsTableColumn.SLICE:
            return 'Index/Slice'
        return None

    def tool_tip(self):
        if self == MetadataSuggestionsTableColumn.FROM:
            return 'Format string to generate the suggestion from. Syntax is the same as FROM in yt-dlp\'s --parse-metadata (ctrl+click to view documentation)'
        if self == MetadataSuggestionsTableColumn.TO:
            return 'Regex to filter the format string. Similar to TO in yt-dlp\'s --parse-metadata, but only the first capture group will be kept (ctrl+click to view documentation)'
        if self == MetadataSuggestionsTableColumn.REPLACE_REGEX:
            return 'Regex to replace in the filtered string. Same as REGEX in yt-dlp\'s --replace-in-metadata (ctrl+click to view documentation)'
        if self == MetadataSuggestionsTableColumn.REPLACE_WITH:
            return 'Format string to replace the regex with. Same as REPLACE in yt-dlp\'s --replace-in-metadata, but the string may also be formatted like FROM in --parse-metadata (ctrl+click to view documentation)'
        if self == MetadataSuggestionsTableColumn.SPLIT:
            return r'Comma-separated list of separators along each of which the resulting string will be split. Every split entry will become one suggestion. A comma inside a separator has to be escaped like \,'
        if self == MetadataSuggestionsTableColumn.SLICE:
            return 'Index or python slice to process the resulting split'
        return None

    def doc_url(self):
        if self in (MetadataSuggestionsTableColumn.FROM, MetadataSuggestionsTableColumn.TO,
                    MetadataSuggestionsTableColumn.REPLACE_REGEX, MetadataSuggestionsTableColumn.REPLACE_WITH):
            return 'https://github.com/yt-dlp/yt-dlp/tree/master?tab=readme-ov-file#modifying-metadata'
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
        if orientation == QtCore.Qt.Orientation.Horizontal:
            if role == QtCore.Qt.ItemDataRole.DisplayRole:
                return str(MetadataSuggestionsTableColumn(section))
            if role == QtCore.Qt.ItemDataRole.ToolTipRole:
                return MetadataSuggestionsTableColumn(section).tool_tip()
        elif orientation == QtCore.Qt.Orientation.Vertical:
            if role == QtCore.Qt.ItemDataRole.DisplayRole:
                return str(section + 1)
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
        return dict(zip(MetadataSuggestionsTableColumn.__members__.values(),
                        [suggestion.pattern_from, suggestion.pattern_to, suggestion.replace_regex,
                         suggestion.replace_with, suggestion.split_separators, suggestion.split_slice]))

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
