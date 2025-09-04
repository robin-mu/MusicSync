from PySide6.QtCore import Qt
from PySide6.QtGui import QAction
from PySide6.QtWidgets import QMainWindow, QMenu

from gui import Ui_MainWindow
from models.collection_tree import FoldersTreeModel, FolderType, Folder


class MainWindow(QMainWindow, Ui_MainWindow):
    def __init__(self):
        super(MainWindow, self).__init__()
        self.setupUi(self)

        self.treeView.setModel(FoldersTreeModel('folders.csv'))
        self.treeView.expandAll()
        self.treeView.setContextMenuPolicy(Qt.CustomContextMenu)
        self.treeView.customContextMenuRequested.connect(self.tree_context_menu)
        self.treeView.selectionModel().selectionChanged.connect(self.tree_selection_changed)

    def tree_selection_changed(self):
        self.treeView.selectedIndexes()[0].model().dataChanged.disconnect()

    def tree_context_menu(self, point):
        index = self.treeView.indexAt(point)
        if index.model() is None:
            return

        parent = index.model().itemFromIndex(index)

        def add_folder(type: FolderType):
            model = index.model()

            new_folder = model.add_folder(parent, type)
            new_folder.setEditable(True)

            new_index = model.indexFromItem(new_folder)
            self.treeView.setCurrentIndex(new_index)
            self.treeView.edit(new_index)

            def name_selected():
                new_folder.name = new_folder.text()
                new_folder.setEditable(False)

            model.dataChanged.connect(name_selected)

        def remove_folder():
            model = index.model()
            model.remove_folder(parent)

        menu = QMenu(self.treeView)

        if parent.type == FolderType.FOLDER:
            add_folder_action = QAction('Add Folder')
            add_folder_action.triggered.connect(lambda: add_folder(FolderType.FOLDER))
            menu.addAction(add_folder_action)

            add_collection_action = QAction('Add Collection')
            add_collection_action.triggered.connect(lambda: add_folder(FolderType.COLLECTION))
            menu.addAction(add_collection_action)

        delete_action = QAction('Delete')
        delete_action.triggered.connect(remove_folder)
        menu.addAction(delete_action)

        menu.exec(self.treeView.viewport().mapToGlobal(point))
