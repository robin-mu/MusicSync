from PySide6 import QtCore
from PySide6.QtCore import Qt, QItemSelection
from PySide6.QtGui import QAction, QCloseEvent, QCursor, QIcon
from PySide6.QtWidgets import QMainWindow, QMenu, QFileDialog, QMessageBox, QInputDialog, QTreeWidgetItem, QTreeWidget, \
    QDialogButtonBox

from src.gui.bookmark_window import BookmarkWindow
from src.gui.main_gui import Ui_MainWindow
from src.gui.models.library import LibraryModel, FolderItem, CollectionItem, CollectionUrlItem


class MainWindow(QMainWindow, Ui_MainWindow):
    def __init__(self):
        super(MainWindow, self).__init__()
        self.setupUi(self)

        self.treeView.setModel(LibraryModel())
        self.treeView.selectionModel().selectionChanged.connect(self.tree_selection_changed)
        self.treeView.setContextMenuPolicy(Qt.CustomContextMenu)
        self.treeView.customContextMenuRequested.connect(self.tree_context_menu)

        self.actionNew_library.triggered.connect(self.new_library)
        self.actionOpen_library.triggered.connect(self.open_library)
        self.actionSave_library.triggered.connect(self.save_library)
        self.actionSave_library_as.triggered.connect(self.save_library_as)
        self.actionChange_Track_Metdata_Table.triggered.connect(self.change_metadata_table)

        self.settings_path_browse.pressed.connect(self.browse_folder_path)
        self.settings_save.pressed.connect(self.save_settings)
        self.settings_sync_button.pressed.connect(self.change_sync_folder)
        self.settings_stop_sync_button.pressed.connect(self.stop_sync)

        self.metadata_table_label.mousePressEvent = self.change_metadata_table
        self.metadata_table_label.setCursor(QCursor(QtCore.Qt.PointingHandCursor))

    def new_library(self):
        if self.treeView.model().has_changed():
            answer = QMessageBox.question(self, 'Save File', 'The current file has not been saved yet. Do you want to save it?', QMessageBox.Yes | QMessageBox.No | QMessageBox.Cancel)

            if answer == QMessageBox.Yes:
                if not self.save_library():
                    return
            elif answer == QMessageBox.Cancel:
                return

        self.treeView.setModel(LibraryModel())
        self.treeView.selectionModel().selectionChanged.connect(self.tree_selection_changed)
        self.update_metadata_table_label()

    def open_library(self):
        if self.treeView.model().has_changed():
            answer = QMessageBox.question(self, 'Save Library', 'The current library has not been saved yet. Do you want to save it?', QMessageBox.Yes | QMessageBox.No | QMessageBox.Cancel)

            if answer == QMessageBox.Yes:
                if not self.save_library():
                    return
            elif answer == QMessageBox.Cancel:
                return

        filename, ok = QFileDialog.getOpenFileName(self, 'Select a file to load', filter="XML files (*.xml)")
        if filename:
            self.treeView.setModel(LibraryModel(filename))
            self.treeView.selectionModel().selectionChanged.connect(self.tree_selection_changed)
            self.treeView.expandAll()
            self.update_metadata_table_label(self.treeView.model().metadata_table_path)

    def save_library(self):
        if self.treeView.model().path:
            self.treeView.model().to_xml()
            return True

        return self.save_library_as()

    def save_library_as(self):
        filename, ok = QFileDialog.getSaveFileName(self, 'Select a file to save to', filter="XML files (*.xml)")
        if filename:
            if not filename.endswith('.xml'):
                filename += '.xml'

            self.treeView.model().to_xml(filename)
            return True
        return False

    def change_metadata_table(self, *args):
        dialog = QFileDialog(self)
        dialog.setWindowTitle('Select a metadata table to associate this library with')
        dialog.setNameFilter('CSV files (*.csv)')
        dialog.setFileMode(QFileDialog.FileMode.AnyFile)

        if dialog.exec():
            self.treeView.model().metadata_table_path = dialog.selectedFiles()[0]
            self.update_metadata_table_label(dialog.selectedFiles()[0])

    def tree_selection_changed(self, selected: QItemSelection, deselected: QItemSelection):
        if deselected.indexes():
            previous_item = self.treeView.model().itemFromIndex(deselected.indexes()[0])
            if isinstance(previous_item, CollectionItem):
                self.save_settings(previous_item)

        if not selected.indexes():
            return

        item = self.treeView.model().itemFromIndex(selected.indexes()[0])

        if isinstance(item, CollectionUrlItem):
            item = item.parent()

        if isinstance(item, CollectionItem):
            self.settings_folder_path.setText(item.folder_path)
            self.settings_filename_format.setText(item.filename_format)
            self.settings_file_extension.setText(item.file_extension)
            self.settings_subfolder.setChecked(item.save_playlists_to_subfolders)
            if item.sync_bookmark_file:
                font = self.settings_folder_path.font()
                font.setItalic(False)
                self.settings_bookmark_file_label.setFont(font)
                self.settings_bookmark_folder_label.setFont(font)

                self.settings_bookmark_file_label.setText(item.sync_bookmark_file)
                self.settings_bookmark_folder_label.setText(item.sync_bookmark_folder)
            else:
                font = self.settings_folder_path.font()
                font.setItalic(True)
                self.settings_bookmark_file_label.setFont(font)
                self.settings_bookmark_folder_label.setFont(font)

                self.settings_bookmark_file_label.setText('Not syncing')
                self.settings_bookmark_folder_label.setText('Not syncing')


            self.entries_stack.setCurrentIndex(0)
            self.settings_stack.setCurrentIndex(0)
        else:
            self.entries_stack.setCurrentIndex(1)
            self.settings_stack.setCurrentIndex(1)

    def save_settings(self, item: CollectionItem = None):
        if item is None:
            item = self.treeView.model().itemFromIndex(self.treeView.currentIndex())
        if item is None or isinstance(item, FolderItem):
            return
        if isinstance(item, CollectionUrlItem):
            item = item.parent()

        item.folder_path = self.settings_folder_path.text()
        item.filename_format = self.settings_filename_format.text()
        item.file_extension = self.settings_file_extension.text()
        item.save_playlists_to_subfolders = self.settings_subfolder.isChecked()

        if self.settings_bookmark_file_label.font().italic():
            item.sync_bookmark_file = ''
            item.sync_bookmark_folder = ''
        else:
            item.sync_bookmark_file = self.settings_bookmark_file_label.text()
            item.sync_bookmark_folder = self.settings_bookmark_folder_label.text()

    def browse_folder_path(self):
        folder = QFileDialog.getExistingDirectory(self, 'Select a directory')
        if folder:
            self.settings_folder_path.setText(folder)

    def change_sync_folder(self):
        def selection_changed(selected: QItemSelection, deselected: QItemSelection):
            if bookmark_window.bookmark_tree_widget.itemFromIndex(selected.indexes()[0]).text(2) == '':
                bookmark_window.buttonBox.button(QDialogButtonBox.Ok).setEnabled(True)
            else:
                bookmark_window.buttonBox.button(QDialogButtonBox.Ok).setEnabled(False)

        bookmark_window = BookmarkWindow()
        bookmark_window.subfolder_check_box.setCheckable(False)
        bookmark_window.bookmark_tree_widget.setSelectionMode(QTreeWidget.SingleSelection)
        bookmark_window.bookmark_tree_widget.selectionModel().selectionChanged.connect(selection_changed)

        if bookmark_window.exec() and bookmark_window.bookmark_tree_widget.selectedItems():
            file = bookmark_window.bookmark_path_entry.text()
            idx = bookmark_window.bookmark_tree_widget.selectedIndexes()[0]
            folder = bookmark_window.bookmark_tree_widget.itemFromIndex(idx).text(0)
            while (parent := bookmark_window.bookmark_tree_widget.itemFromIndex(idx.parent())) is not None:
                folder = f'{parent.text(0)}/{folder}'
                idx = idx.parent()

            self.settings_bookmark_file_label.setText(file)
            self.settings_bookmark_folder_label.setText(folder)

    def stop_sync(self):
        font = self.settings_bookmark_file_label.font()
        font.setItalic(True)
        self.settings_bookmark_file_label.setFont(font)
        self.settings_bookmark_folder_label.setFont(font)
        self.settings_bookmark_folder_label.setText('Not syncing')
        self.settings_bookmark_file_label.setText('Not syncing')

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

        def remove():
            current_index = self.treeView.currentIndex()
            parent_index = self.treeView.currentIndex().parent()
            self.treeView.model().removeRow(current_index.row(), parent_index)

        def add_url():
            url, ok = QInputDialog.getText(self, 'Add URL', 'Enter URL:')
            if url:
                self.treeView.model().add_url(parent, url)

        def import_from_bookmarks():
            bookmark_window = BookmarkWindow(self)
            if bookmark_window.exec():
                urls = []
                def add_urls(item: QTreeWidgetItem, recursion_depth=None):
                    if item.childCount() > 0 and (recursion_depth is None or recursion_depth > 0):
                        for i in range(item.childCount()):
                            add_urls(item.child(i), None if recursion_depth is None else recursion_depth - 1)
                    elif item.text(2):
                        data = {'url': item.text(2)}
                        if bookmark_window.bookmark_title_check_box.isChecked():
                            data['name'] = item.text(0)

                        urls.append(data)

                for item in bookmark_window.bookmark_tree_widget.selectedItems():
                    add_urls(item, recursion_depth=None if bookmark_window.subfolder_check_box.isChecked() else 1)

                for data in urls:
                    self.treeView.model().add_url(parent, **data)

        menu = QMenu(self.treeView)

        if isinstance(parent, FolderItem) or index.model() is None:
            add_folder_action = QAction('Add Folder')
            add_folder_action.setIcon(QIcon.fromTheme(QIcon.ThemeIcon.FolderNew))
            add_folder_action.triggered.connect(lambda: add_folder(True))
            menu.addAction(add_folder_action)

            add_collection_action = QAction('Add Collection')
            add_collection_action.setIcon(QIcon.fromTheme(QIcon.ThemeIcon.ContactNew))
            add_collection_action.triggered.connect(lambda: add_folder(False))
            menu.addAction(add_collection_action)
        elif isinstance(parent, CollectionItem):
            add_url_action = QAction('Add URL')
            add_url_action.setIcon(QIcon.fromTheme('list-add'))
            add_url_action.triggered.connect(add_url)
            menu.addAction(add_url_action)

            import_urls_from_bookmarks_action = QAction('Import URLs From Bookmarks')
            import_urls_from_bookmarks_action.triggered.connect(import_from_bookmarks)
            menu.addAction(import_urls_from_bookmarks_action)

        if index.model() is not None:
            delete_action = QAction('Delete')
            delete_action.setIcon(QIcon.fromTheme(QIcon.ThemeIcon.EditDelete))
            delete_action.triggered.connect(remove)
            menu.addAction(delete_action)

        menu.exec(self.treeView.viewport().mapToGlobal(point))

    def update_metadata_table_label(self, path=''):
        if path:
            self.metadata_table_label.setText(f'Current track metadata table: {path} (Click to change)')
        else:
            self.metadata_table_label.setText('This library has no track metadata table associated with it. (Click to add one)')

    def closeEvent(self, event: QCloseEvent):
        self.save_settings()
        if self.treeView.model().has_changed():
            answer = QMessageBox.question(self, 'Save Library',
                                          'The current library has not been saved yet. Do you want to save it?',
                                          QMessageBox.Yes | QMessageBox.No | QMessageBox.Cancel)

            if answer == QMessageBox.Yes:
                if self.save_library():
                    event.accept()
                else:
                    event.ignore()
            elif answer == QMessageBox.Cancel:
                event.ignore()
            elif answer == QMessageBox.No:
                event.accept()