from PySide6 import QtCore

from src.music_sync_library import MetadataColumn


class MetadataColumnModel(QtCore.QAbstractTableModel):
    def __init__(self, columns: list[MetadataColumn], parent: 'MetadataSuggestionsDialog'=None):
        super(MetadataColumnModel, self).__init__(parent)

        self.parent = parent
        self.columns = columns

    def rowCount(self, parent: QtCore.QModelIndex = QtCore.QModelIndex()):
        return len(self.columns)

    def columnCount(self, parent: QtCore.QModelIndex = QtCore.QModelIndex()):
        return 4

    def data(self, index, /, role = QtCore.Qt.ItemDataRole.DisplayRole):
        if not index.isValid():
            return None

        data = self.columns[index.row()].to_row()[index.column()]
        if role == QtCore.Qt.ItemDataRole.BackgroundRole:
            return data

        if role == QtCore.Qt.ItemDataRole.DisplayRole and index.column() == 0:
            return data

        return None

    def headerData(self, section, orientation, /, role = ...):
        if role == QtCore.Qt.ItemDataRole.DisplayRole and orientation == QtCore.Qt.Orientation.Horizontal:
            if section == 0:
                return 'Name'
            if section == 1:
                return 'Show format \noptions'
            if section == 2:
                return 'Default for format \noption "Format as title"'
            if section == 3:
                return 'Default for format \noption "Remove brackets"'
        return None

    def setData(self, index, value, /, role=QtCore.Qt.ItemDataRole.EditRole):
        if index.isValid():
            self.columns[index.row()].set_from_column(index.column(), value)
            if index.column() == 1:
                self.parent.columns_table.itemDelegateForColumn(2).refresh_editor()
                self.parent.columns_table.itemDelegateForColumn(3).refresh_editor()
            return True

        return False

    def flags(self, index):
        return QtCore.Qt.ItemFlag.ItemIsEditable | QtCore.Qt.ItemFlag.ItemIsEnabled

