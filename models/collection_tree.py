import enum
import json
import pandas as pd

from PySide6.QtGui import QStandardItemModel, QStandardItem

from enum import Enum

class FolderType(Enum):
    FOLDER = 'folder'
    COLLECTION = 'collection'


class Folder(QStandardItem):
    def __init__(self, type, parent, name='', settings=None):
        super(Folder, self).__init__()
        self.name = name
        self.type = type
        self.parent = parent
        self.settings = settings

        self.setText(self.name)
        self.setEditable(False)


class FoldersTreeModel(QStandardItemModel):
    def __init__(self, csv_file):
        super(FoldersTreeModel, self).__init__()
        self.df = pd.read_csv(csv_file, index_col='id')
        self.root = self.invisibleRootItem()
        self.folders: dict[int, Folder] = {}

        for row in self.df.itertuples():
            self.folders[row.Index] = Folder(name=row.name, type=FolderType(row.type), parent=row.parent, settings=row.settings)

        for row in self.df.itertuples():
            if pd.notna(row.parent):
                self.folders[row.parent].appendRow(self.folders[row.Index])
            else:
                self.root.appendRow(self.folders[row.Index])

    def add_folder(self, folder, parent):
        parent.appendRow(folder)
        self.folders[max(self.folders.keys()) + 1] = folder
