import pandas as pd
from PySide6 import QtCore
from PySide6.QtCore import QAbstractTableModel, QModelIndex


class DataFrameTableModel(QAbstractTableModel):
    def __init__(self, df=pd.DataFrame, parent=None):
        super().__init__(parent)

        self.parent = parent
        self.df = df

    def delegate_columns(self) -> list[int]:
        return []

    def column_display_name(self, col: int) -> str | None:
        return None

    def display_data(self, value) -> str:
        return str(value)

    def rowCount(self, parent: QModelIndex = ...) -> int:
        return len(self.df)

    def columnCount(self, parent: QModelIndex = ...) -> int:
        return len(self.df.columns)

    def data(self, index, /, role=QtCore.Qt.ItemDataRole.DisplayRole):
        if not index.isValid():
            return None

        if role == QtCore.Qt.ItemDataRole.DisplayRole and index.column() not in self.delegate_columns():
            return self.display_data(self.df.iloc[index.row(), index.column()])
        elif role == QtCore.Qt.ItemDataRole.BackgroundRole:
            return self.df.iloc[index.row(), index.column()]
        else:
            return None

    def headerData(self, section, orientation, /, role=...):
        if orientation == QtCore.Qt.Orientation.Horizontal and role == QtCore.Qt.ItemDataRole.DisplayRole:
            display_name = self.column_display_name(section)
            if display_name is not None:
                return display_name
            else:
                return self.df.columns[section]
        return None

    def setData(self, index, value, /, role=QtCore.Qt.ItemDataRole.EditRole):
        if role != QtCore.Qt.ItemDataRole.EditRole:
            return False
        if index.isValid():
            self.df.iloc[index.row(), index.column()] = value
            return True

        return False

    def flags(self, index):
        return QtCore.Qt.ItemFlag.ItemIsEnabled | QtCore.Qt.ItemFlag.ItemIsSelectable