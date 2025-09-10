from PySide6.QtCore import Qt, QItemSelection
from PySide6.QtGui import QAction, QCloseEvent
from PySide6.QtWidgets import QMainWindow, QMenu, QFileDialog, QMessageBox, QInputDialog

from gui import Ui_MainWindow
from models.library import LibraryModel, Folder, Collection, CollectionUrl


class MainWindow(QMainWindow, Ui_MainWindow):
    def __init__(self):
        super(MainWindow, self).__init__()
        self.setupUi(self)

        self.treeView.setModel(LibraryModel())
        self.treeView.selectionModel().selectionChanged.connect(self.tree_selection_changed)
        self.treeView.setContextMenuPolicy(Qt.CustomContextMenu)
        self.treeView.customContextMenuRequested.connect(self.tree_context_menu)
        self.model_changed = False
        self.treeView.model().dataChanged.connect(self.change_model)

        self.actionLoad_folders_xml_file.triggered.connect(self.load_folders_xml_file)
        self.actionSave_folders_xml_file.triggered.connect(self.save_folders_xml_file)
        self.actionChange_track_table.triggered.connect(self.change_metadata_table)

        self.settings_path_browse.pressed.connect(self.browse_folder_path)
        self.settings_save.pressed.connect(self.save_settings)

    def change_model(self):
        print("change_model")
        self.model_changed = True

    def load_folders_xml_file(self):
        if self.treeView.model().root.rowCount() > 0 and self.model_changed:
            answer = QMessageBox.question(self, 'Save File', 'The current file has not been saved yet. Do you want to save it?', QMessageBox.Yes | QMessageBox.No | QMessageBox.Cancel)

            if answer == QMessageBox.Yes:
                if not self.save_folders_xml_file():
                    return
            elif answer == QMessageBox.Cancel:
                return

        filename, ok = QFileDialog.getOpenFileName(self, 'Select a file to load', filter="XML files (*.xml)")
        if filename:
            self.treeView.setModel(LibraryModel(filename))
            self.treeView.selectionModel().selectionChanged.connect(self.tree_selection_changed)
            self.treeView.model().dataChanged.connect(self.change_model)
            self.treeView.expandAll()
            self.model_changed = False

    def save_folders_xml_file(self):
        filename, ok = QFileDialog.getSaveFileName(self, 'Select a file to save to', filter="XML files (*.xml)")
        if filename:
            if not filename.endswith('.xml'):
                filename += '.xml'

            self.treeView.model().to_xml(filename)
            self.model_changed = False
            return True
        return False

    def change_metadata_table(self):
        filename, ok = QFileDialog.getOpenFileName(self, 'Select a metadata table to associate this library with', filter="CSV files (*.csv)")
        if filename:
            self.treeView.model().track_table_path = filename

    def tree_selection_changed(self, selected: QItemSelection, deselected: QItemSelection):
        if deselected.indexes():
            previous_item = self.treeView.model().itemFromIndex(deselected.indexes()[0])
            if isinstance(previous_item, Collection):
                self.save_settings(previous_item)

        if not selected.indexes():
            return

        item = self.treeView.model().itemFromIndex(selected.indexes()[0])

        if isinstance(item, CollectionUrl):
            item = item.parent()

        if isinstance(item, Collection):
            self.settings_folder_path.setText(item.folder_path)
            self.settings_filename_format.setText(item.filename_format)
            self.settings_file_extension.setText(item.file_extension)
            self.settings_subfolder.setChecked(item.save_playlists_to_subfolders)

            self.entries_stack.setCurrentIndex(0)
            self.settings_stack.setCurrentIndex(0)
        else:
            self.entries_stack.setCurrentIndex(1)
            self.settings_stack.setCurrentIndex(1)

    def save_settings(self, item: Collection = None):
        if item is None:
            item = self.treeView.model().itemFromIndex(self.treeView.currentIndex())
        if item is None or isinstance(item, Folder):
            return
        if isinstance(item, CollectionUrl):
            item = item.parent()

        if (item.folder_path == self.settings_folder_path.text() and
                item.filename_format == self.settings_filename_format.text() and
                item.file_extension == self.settings_file_extension.text() and
                item.save_playlists_to_subfolders == self.settings_subfolder.isChecked()):
            return

        item.folder_path = self.settings_folder_path.text()
        item.filename_format = self.settings_filename_format.text()
        item.file_extension = self.settings_file_extension.text()
        item.save_playlists_to_subfolders = self.settings_subfolder.isChecked()

        item.emitDataChanged()

    def browse_folder_path(self):
        folder = QFileDialog.getExistingDirectory(self, 'Select a directory')
        if folder:
            self.settings_folder_path.setText(folder)

    def tree_context_menu(self, point):
        index = self.treeView.indexAt(point)
        if index.model() is None:
            parent = self.treeView.model().root
        else:
            parent = index.model().itemFromIndex(index)

        def add_folder(is_folder: bool):
            model = index.model() or self.treeView.model()

            if is_folder:
                new_folder = model.add_folder(parent)
            else:
                new_folder = model.add_collection(parent)

            new_index = model.indexFromItem(new_folder)
            self.treeView.setCurrentIndex(new_index)
            self.treeView.edit(new_index)

            new_folder.emitDataChanged()

        def remove():
            current_index = self.treeView.currentIndex()
            parent = self.treeView.currentIndex().parent()
            self.treeView.model().removeRow(current_index.row(), parent)

            self.treeView.model().itemFromIndex(parent).emitDataChanged()

        def add_url():
            url, ok = QInputDialog.getText(self, 'Add URL', 'Enter URL:')
            if url:
                new_url = self.treeView.model().add_url(parent, url)
                new_url.emitDataChanged()

        menu = QMenu(self.treeView)

        if isinstance(parent, Folder) or index.model() is None:
            add_folder_action = QAction('Add Folder')
            add_folder_action.triggered.connect(lambda: add_folder(True))
            menu.addAction(add_folder_action)

            add_collection_action = QAction('Add Collection')
            add_collection_action.triggered.connect(lambda: add_folder(False))
            menu.addAction(add_collection_action)
        elif isinstance(parent, Collection):
            add_url_action = QAction('Add URL')
            add_url_action.triggered.connect(add_url)
            menu.addAction(add_url_action)

        if index.model() is not None:
            delete_action = QAction('Delete')
            delete_action.triggered.connect(remove)
            menu.addAction(delete_action)

        menu.exec(self.treeView.viewport().mapToGlobal(point))

    def closeEvent(self, event: QCloseEvent):
        self.save_settings()
        if self.model_changed:
            answer = QMessageBox.question(self, 'Save File',
                                          'The current file has not been saved yet. Do you want to save it?',
                                          QMessageBox.Yes | QMessageBox.No | QMessageBox.Cancel)

            if answer == QMessageBox.Yes:
                if not self.save_folders_xml_file():
                    event.ignore()
                else:
                    event.accept()
            elif answer == QMessageBox.Cancel:
                event.ignore()
            elif answer == QMessageBox.No:
                event.accept()