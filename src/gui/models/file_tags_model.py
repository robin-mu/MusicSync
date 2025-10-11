from enum import IntEnum
from typing import Any

from PySide6 import QtCore
from PySide6.QtCore import QModelIndex

from src.music_sync_library import FileTag


class FileTagsTableColumn(IntEnum):
    NAME = 0
    FORMAT = 1

    def __str__(self):
        if self == FileTagsTableColumn.NAME:
            return 'Name'
        if self == FileTagsTableColumn.FORMAT:
            return 'Format'
        return None

    def tool_tip(self):
        if self == FileTagsTableColumn.FORMAT:
            return 'The format is the same as yt-dlp\'s output template'
        return None


class FileTagsModel(QtCore.QAbstractTableModel):
    def __init__(self, tags: list[FileTag], parent: 'MetadataSuggestionsDialog'=None):
        super(FileTagsModel, self).__init__(parent)

        self.parent = parent
        self.tags = tags

    def rowCount(self, parent: QtCore.QModelIndex = QtCore.QModelIndex()):
        return len(self.tags)

    def columnCount(self, parent: QtCore.QModelIndex = QtCore.QModelIndex()):
        return len(FileTagsTableColumn.__members__)

    def data(self, index, /, role = QtCore.Qt.ItemDataRole.DisplayRole):
        if not index.isValid():
            return None

        if role in [QtCore.Qt.ItemDataRole.DisplayRole, QtCore.Qt.ItemDataRole.EditRole]:
            return FileTagsModel.field_to_row(self.tags[index.row()])[index.column()]

        return None

    def headerData(self, section, orientation, /, role = ...):
        if role == QtCore.Qt.ItemDataRole.DisplayRole:
            return str(FileTagsTableColumn(section))
        if role == QtCore.Qt.ItemDataRole.ToolTipRole:
            return FileTagsTableColumn(section).tool_tip()
        return None

    def setData(self, index, value, /, role=QtCore.Qt.ItemDataRole.EditRole):
        if index.isValid():
            self.set_field_from_index(index, value)
            return True

        return False

    def flags(self, index):
        return QtCore.Qt.ItemFlag.ItemIsEnabled | QtCore.Qt.ItemFlag.ItemIsSelectable | QtCore.Qt.ItemFlag.ItemIsEditable

    @staticmethod
    def field_to_row(tag: FileTag) -> dict[int, Any]:
        return dict(zip(FileTagsTableColumn.__members__.values(), [tag.name, tag.format]))

    def set_field_from_index(self, index: QModelIndex, value: Any):
        tag = self.tags[index.row()]
        column = index.column()
        if column == FileTagsTableColumn.NAME:
            tag.name = value
        elif column == FileTagsTableColumn.FORMAT:
            tag.format = value
