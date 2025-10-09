from copy import deepcopy

from PySide6 import QtCore
from PySide6.QtCore import Qt, QItemSelection, QEvent, QUrl
from PySide6.QtGui import QAction, QCloseEvent, QIcon, QDesktopServices
from PySide6.QtWidgets import QMainWindow, QMenu, QFileDialog, QMessageBox, QInputDialog, QTreeWidgetItem, QTreeWidget, \
    QDialogButtonBox, QTreeView, QApplication

from src.download.downloader import MusicSyncDownloader
from src.gui.bookmark_dialog import BookmarkDialog
from src.gui.main_gui import Ui_MainWindow
from src.gui.metadata_suggestions_dialog import MetadataSuggestionsDialog
from src.gui.models.library_model import LibraryModel, FolderItem, CollectionItem, CollectionUrlItem
from src.gui.models.sync_action_combobox_model import SyncActionComboboxModel
from src.music_sync_library import TrackSyncStatus, ExternalMetadataTable


class MainWindow(QMainWindow, Ui_MainWindow):
    def __init__(self):
        super(MainWindow, self).__init__()
        self.setupUi(self)

        # Menu bar
        self.actionNew_library.triggered.connect(self.new_library)
        self.actionOpen_library.triggered.connect(self.open_library)
        self.actionSave_library.triggered.connect(self.save_library)
        self.actionSave_library_as.triggered.connect(self.save_library_as)
        self.actionChange_Track_Metdata_Table.triggered.connect(self.change_metadata_table)


        # Library Tree View
        self.treeView.setModel(LibraryModel('/home/robin/Desktop/Music-Sync/a.xml'))
        self.treeView.expandAll()

        self.treeView.selectionModel().selectionChanged.connect(self.tree_selection_changed)
        self.treeView.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.treeView.customContextMenuRequested.connect(lambda point: TreeContextMenu(self.treeView, point))


        # File sync status page
        self.sync_button.pressed.connect(self.sync_collection)


        # Collection settings page
        self.settings_path_browse.pressed.connect(self.browse_folder_path)
        self.settings_save.pressed.connect(self.save_settings)
        self.settings_sync_button.pressed.connect(self.change_sync_folder)
        self.settings_stop_sync_button.pressed.connect(lambda: self.update_current_sync_folder(''))
        self.settings_edit_metadata_button.pressed.connect(self.edit_metadata_suggestions)

        self.metadata_table_label.mousePressEvent = self.change_metadata_table

        self.action_combo_boxes = dict(zip([self.added_combo_box, self.not_downloaded_combo_box, self.removed_combo_box, self.local_combo_box, self.permanent_combo_box, self.downloaded_combo_box],
                                   [TrackSyncStatus.ADDED_TO_SOURCE, TrackSyncStatus.NOT_DOWNLOADED, TrackSyncStatus.REMOVED_FROM_SOURCE, TrackSyncStatus.LOCAL_FILE, TrackSyncStatus.PERMANENTLY_DOWNLOADED, TrackSyncStatus.DOWNLOADED]))
        for box, status in self.action_combo_boxes.items():
            box.setModel(SyncActionComboboxModel(status))
            box.highlighted[int].connect(lambda index, box=box: self.show_action_item_tip(box, index))
            box.view().viewport().installEventFilter(self)

        self.settings_filename_format_label.mousePressEvent = self.open_doc_url


    @staticmethod
    def open_doc_url(*_):
        if QApplication.keyboardModifiers() == QtCore.Qt.KeyboardModifier.ControlModifier:
            QDesktopServices.openUrl(QUrl('https://github.com/yt-dlp/yt-dlp/tree/master?tab=readme-ov-file#output-template'))


    def show_action_item_tip(self, box, index):
        tip = box.itemData(index, Qt.ItemDataRole.StatusTipRole)
        self.statusbar.showMessage(tip or '')

    def eventFilter(self, obj, event):
        for box in self.action_combo_boxes.keys():
            if obj is box.view().viewport():
                if event.type() in (QEvent.Type.Leave, QEvent.Type.Hide):
                    self.statusbar.clearMessage()
        return super(MainWindow, self).eventFilter(obj, event)

    def new_library(self):
        if self.treeView.model().has_changed():
            answer = QMessageBox.question(self, 'Save File', 'The current file has not been saved yet. Do you want to save it?', QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No | QMessageBox.StandardButton.Cancel)

            if answer == QMessageBox.StandardButton.Yes:
                if not self.save_library():
                    return
            elif answer == QMessageBox.StandardButton.Cancel:
                return

        self.treeView.setModel(LibraryModel())
        self.treeView.selectionModel().selectionChanged.connect(self.tree_selection_changed)
        self.update_metadata_table_label()

    def open_library(self):
        if self.treeView.model().has_changed():
            answer = QMessageBox.question(self, 'Save Library', 'The current library has not been saved yet. Do you want to save it?', QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No | QMessageBox.StandardButton.Cancel)

            if answer == QMessageBox.StandardButton.Yes:
                if not self.save_library():
                    return
            elif answer == QMessageBox.StandardButton.Cancel:
                return

        filename, ok = QFileDialog.getOpenFileName(self, 'Select a file to load', filter="XML files (*.xml) (*.xml)")
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
        filename, ok = QFileDialog.getSaveFileName(self, 'Select a file to save to', filter="XML files (*.xml) (*.xml)")
        if filename:
            if not filename.endswith('.xml'):
                filename += '.xml'

            self.treeView.model().to_xml(filename)
            self.treeView.model().path = filename
            return True
        return False

    def change_metadata_table(self, *_):
        dialog = QFileDialog(self)
        dialog.setWindowTitle('Select a metadata table to associate this library with')
        dialog.setNameFilter('CSV files (*.csv)')
        dialog.setFileMode(QFileDialog.FileMode.AnyFile)

        if dialog.exec():
            self.treeView.model().metadata_table_path = dialog.selectedFiles()[0]
            self.update_metadata_table_label(dialog.selectedFiles()[0])

    def tree_selection_changed(self, selected: QItemSelection, deselected: QItemSelection):
        if not selected.indexes():
            return

        selected_collection = self.treeView.model().itemFromIndex(selected.indexes()[0])

        if isinstance(selected_collection, CollectionUrlItem):
            selected_collection = selected_collection.parent()

        if deselected.indexes():
            deselected_collection = self.treeView.model().itemFromIndex(deselected.indexes()[0])
            if isinstance(deselected_collection, CollectionUrlItem):
                deselected_collection = deselected_collection.parent()

            if isinstance(deselected_collection, CollectionItem):
                if selected_collection == deselected_collection:
                    return
                self.save_settings(deselected_collection)

        if isinstance(selected_collection, CollectionItem):
            self.settings_folder_path.setText(selected_collection.folder_path)
            self.settings_filename_format.setText(selected_collection.filename_format)
            self.settings_file_extension.setText(selected_collection.file_extension)
            self.settings_subfolder.setChecked(selected_collection.save_playlists_to_subfolders)
            self.settings_exclude_urls_checkbox.setChecked(selected_collection.exclude_after_download)

            self.update_current_sync_folder(selected_collection.sync_bookmark_file, selected_collection.sync_bookmark_path, selected_collection.sync_bookmark_title_as_url_name)

            for box, status in self.action_combo_boxes.items():
                box.setCurrentIndex(box.findText(selected_collection.sync_actions[status].gui_string))

            self.update_metadata_suggestions_label()
            self.update_tags_label()

            self.sync_stack.setCurrentIndex(1)
            self.metadata_stack.setCurrentIndex(1)
            self.tags_stack.setCurrentIndex(1)
            self.settings_stack.setCurrentIndex(1)
        else:
            self.sync_stack.setCurrentIndex(0)
            self.metadata_stack.setCurrentIndex(0)
            self.tags_stack.setCurrentIndex(0)
            self.settings_stack.setCurrentIndex(0)

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
        item.exclude_after_download = self.settings_exclude_urls_checkbox.isChecked()
        item.sync_actions = {
            TrackSyncStatus.ADDED_TO_SOURCE: self.added_combo_box.model().invisibleRootItem().child(self.added_combo_box.currentIndex()).action,
            TrackSyncStatus.NOT_DOWNLOADED: self.not_downloaded_combo_box.model().invisibleRootItem().child(self.not_downloaded_combo_box.currentIndex()).action,
            TrackSyncStatus.REMOVED_FROM_SOURCE: self.removed_combo_box.model().invisibleRootItem().child(self.removed_combo_box.currentIndex()).action,
            TrackSyncStatus.LOCAL_FILE: self.local_combo_box.model().invisibleRootItem().child(self.local_combo_box.currentIndex()).action,
            TrackSyncStatus.PERMANENTLY_DOWNLOADED: self.permanent_combo_box.model().invisibleRootItem().child(self.permanent_combo_box.currentIndex()).action,
            TrackSyncStatus.DOWNLOADED: self.downloaded_combo_box.model().invisibleRootItem().child(self.downloaded_combo_box.currentIndex()).action,
        }

    def browse_folder_path(self):
        folder = QFileDialog.getExistingDirectory(self, 'Select a directory')
        if folder:
            self.settings_folder_path.setText(folder)

    def get_selected_collection(self) -> CollectionItem:
        current_collection = self.treeView.model().itemFromIndex(self.treeView.selectedIndexes()[0])
        if isinstance(current_collection, CollectionUrlItem):
            current_collection = current_collection.parent()
        return current_collection


    def update_current_sync_folder(self, file: str, path: list[tuple[str, str]]=None, set_url_name=False):
        current_collection = self.get_selected_collection()
        current_collection.sync_bookmark_file = file
        current_collection.sync_bookmark_path = path or []
        current_collection.sync_bookmark_title_as_url_name = set_url_name

        if file:
            font = self.settings_folder_path.font()
            font.setItalic(False)
            self.settings_bookmark_file_label.setFont(font)
            self.settings_bookmark_folder_label.setFont(font)

            self.settings_bookmark_file_label.setText(file)
            self.settings_bookmark_folder_label.setText('/'.join([e[1] for e in path]))
        else:
            font = self.settings_folder_path.font()
            font.setItalic(True)
            self.settings_bookmark_file_label.setFont(font)
            self.settings_bookmark_folder_label.setFont(font)

            self.settings_bookmark_file_label.setText('Not syncing')
            self.settings_bookmark_folder_label.setText('Not syncing')

    def change_sync_folder(self):
        def selection_changed(selected: QItemSelection, _: QItemSelection):
            if bookmark_window.bookmark_tree_widget.itemFromIndex(selected.indexes()[0]).text(2) == '':
                bookmark_window.buttonBox.button(QDialogButtonBox.StandardButton.Ok).setEnabled(True)
            else:
                bookmark_window.buttonBox.button(QDialogButtonBox.StandardButton.Ok).setEnabled(False)

        bookmark_window = BookmarkDialog()
        bookmark_window.subfolder_check_box.setEnabled(False)
        bookmark_window.bookmark_tree_widget.setSelectionMode(QTreeWidget.SelectionMode.SingleSelection)
        bookmark_window.bookmark_tree_widget.selectionModel().selectionChanged.connect(selection_changed)

        if bookmark_window.exec() and bookmark_window.bookmark_tree_widget.selectedItems():
            file = bookmark_window.bookmark_path_entry.text()
            idx = bookmark_window.bookmark_tree_widget.selectedIndexes()[0]
            folder = []
            while (item := bookmark_window.bookmark_tree_widget.itemFromIndex(idx)) is not None:
                folder.append((item.text(3), item.text(0)))
                idx = idx.parent()

            self.update_current_sync_folder(file, folder[::-1], bookmark_window.bookmark_title_check_box.isChecked())

    def edit_metadata_suggestions(self):
        tables = ([ExternalMetadataTable(id=0,
                                        name='Table of this library',
                                        path=self.treeView.model().metadata_table_path)] +
                  deepcopy(self.treeView.model().external_metadata_tables))
        current_collection = self.get_selected_collection()
        metadata_suggestions_dialog = MetadataSuggestionsDialog(deepcopy(current_collection.metadata_suggestions),
                                                                tables,
                                                                deepcopy(current_collection.file_tags),
                                                                parent=self)

        if metadata_suggestions_dialog.exec():
            current_collection.metadata_suggestions = metadata_suggestions_dialog.fields_table.model().fields
            current_collection.file_tags = metadata_suggestions_dialog.tags_table.model().tags
            self.treeView.model().external_metadata_tables = metadata_suggestions_dialog.external_tables_table.model().tables[1:]
            self.update_metadata_suggestions_label()
            self.update_tags_label()

    def update_metadata_suggestions_label(self):
        suggestions = [s.name for s in self.get_selected_collection().metadata_suggestions]
        self.settings_fields_label.setText(self.settings_fields_label.text().split(': ')[0] + ': ' + ', '.join(suggestions))

    def update_tags_label(self):
        tags = [t.name for t in self.get_selected_collection().file_tags]
        self.settings_tags_label.setText(self.settings_tags_label.text().split(': ')[0] + ': ' + ', '.join(tags))

    def update_metadata_table_label(self, path=''):
        if path:
            self.metadata_table_label.setText(f'Current track metadata table: {path} (Click to change)')
        else:
            self.metadata_table_label.setText('This library has no track metadata table associated with it. (Click to add one)')

    def sync_collection(self):
        downloader = MusicSyncDownloader()
        downloader.update_sync_status(self.get_selected_collection().to_xml_object())

    def closeEvent(self, event: QCloseEvent):
        self.save_settings()
        if self.treeView.model().has_changed():
            answer = QMessageBox.question(self, 'Save Library',
                                          'The current library has not been saved yet. Do you want to save it?',
                                          QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No | QMessageBox.StandardButton.Cancel)

            if answer == QMessageBox.StandardButton.Yes:
                if self.save_library():
                    event.accept()
                else:
                    event.ignore()
            elif answer == QMessageBox.StandardButton.Cancel:
                event.ignore()
            elif answer == QMessageBox.StandardButton.No:
                event.accept()

class TreeContextMenu(QMenu):
    def __init__(self, parent: QTreeView, point):
        super().__init__(parent)
        self.parent = parent
        self.model: LibraryModel = parent.model()

        self.index = parent.indexAt(point)

        if self.index.model() is None:
            self.item = self.model.root
        else:
            self.item = self.model.itemFromIndex(self.index)

        if isinstance(self.item, FolderItem) or self.index.model() is None:
            add_folder_action = QAction('Add Folder')
            add_folder_action.setIcon(QIcon.fromTheme(QIcon.ThemeIcon.FolderNew))
            add_folder_action.triggered.connect(lambda: self.add_folder(True))
            self.addAction(add_folder_action)

            add_collection_action = QAction('Add Collection')
            add_collection_action.setIcon(QIcon.fromTheme(QIcon.ThemeIcon.ContactNew))
            add_collection_action.triggered.connect(lambda: self.add_folder(False))
            self.addAction(add_collection_action)
        elif isinstance(self.item, CollectionItem):
            add_url_action = QAction('Add URL')
            add_url_action.setIcon(QIcon.fromTheme('list-add'))
            add_url_action.triggered.connect(self.add_url)
            self.addAction(add_url_action)

            import_urls_from_bookmarks_action = QAction('Import URLs From Bookmarks')
            import_urls_from_bookmarks_action.triggered.connect(self.import_from_bookmarks)
            self.addAction(import_urls_from_bookmarks_action)
        elif isinstance(self.item, CollectionUrlItem):
            exclude_action = QAction('Include URL' if self.item.excluded else 'Exclude URL from downloading')
            exclude_action.triggered.connect(self.toggle_excluded)
            self.addAction(exclude_action)

        if self.index.model() is not None:
            delete_action = QAction('Delete')
            delete_action.setIcon(QIcon.fromTheme(QIcon.ThemeIcon.EditDelete))
            delete_action.triggered.connect(self.remove)
            self.addAction(delete_action)

        self.exec(self.parent.mapToGlobal(point))

    def add_folder(self, is_folder: bool):
        if is_folder:
            new_folder = self.model.add_folder(self.item)
        else:
            new_folder = self.model.add_collection(self.item)

        new_index = self.model.indexFromItem(new_folder)
        self.parent.setCurrentIndex(new_index)
        self.parent.edit(new_index)

    def remove(self):
        parent_index = self.index.parent()
        self.model.removeRow(self.index.row(), parent_index)

    def add_url(self):
        url, ok = QInputDialog.getText(self, 'Add URL', 'Enter URL:')
        if url:
            self.model.add_url(self.item, url)

    def import_from_bookmarks(self):
        bookmark_window = BookmarkDialog(self.parent)
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
                self.model.add_url(self.item, **data)

    def toggle_excluded(self):
        self.item.excluded = not self.item.excluded
        font = self.item.font()
        font.setStrikeOut(not font.strikeOut())
        self.item.setFont(font)
