import sys

from PySide6.QtCore import Qt
from PySide6.QtGui import QAction
from PySide6.QtWidgets import QApplication, QMainWindow, QMenu

from gui import Ui_MainWindow
from models.collection_tree import FoldersTreeModel, FolderType, Folder


class MainWindow(QMainWindow, Ui_MainWindow):
    def __init__(self):
        super(MainWindow, self).__init__()
        self.setupUi(self)

        self.treeView.setModel(FoldersTreeModel('folders.csv'))
        self.treeView.expandAll()
        self.treeView.setContextMenuPolicy(Qt.CustomContextMenu)
        self.treeView.customContextMenuRequested.connect(self.treeContextMenu)

    def treeContextMenu(self, point):
        index = self.treeView.selectedIndexes()[0]
        parent = index.model().itemFromIndex(index)

        if parent.type != FolderType.FOLDER:
            return

        def add_folder(type: FolderType):
            index = self.treeView.selectedIndexes()[0]
            model = index.model()
            parent = model.itemFromIndex(index)

            new_folder = Folder(type, parent)
            new_folder.setEditable(True)
            model.add_folder(new_folder, parent)

            new_index = model.indexFromItem(new_folder)
            self.treeView.setCurrentIndex(new_index)
            self.treeView.edit(new_index)

            model.dataChanged.connect(lambda: new_folder.setEditable(False))

        menu = QMenu(self.treeView)
        add_folder_action = QAction('Add Folder')
        add_folder_action.triggered.connect(lambda: add_folder(FolderType.FOLDER))
        menu.addAction(add_folder_action)
        add_collection_action = QAction('Add Collection')
        add_collection_action.triggered.connect(lambda: add_folder(FolderType.COLLECTION))
        menu.addAction(add_collection_action)

        menu.exec(self.treeView.viewport().mapToGlobal(point))


if __name__ == "__main__":
    app = QApplication(sys.argv)

    window = MainWindow()
    window.show()
    sys.exit(app.exec())