import os.path
from copy import deepcopy

import pandas as pd
from PySide6 import QtCore
from PySide6.QtCore import QEvent, QItemSelection, Qt, QUrl, QThreadPool, Slot
from PySide6.QtGui import QAction, QCloseEvent, QDesktopServices, QIcon
from PySide6.QtWidgets import (
    QApplication,
    QDialogButtonBox,
    QFileDialog,
    QInputDialog,
    QMainWindow,
    QMenu,
    QMessageBox,
    QTreeView,
    QTreeWidget,
    QTreeWidgetItem,
)

from .bookmark_dialog import BookmarkDialog
from .main_gui import Ui_MainWindow
from .metadata_suggestions_dialog import MetadataSuggestionsDialog
from .models.file_sync_model import ActionComboboxDelegate, FileSyncModel, FileSyncModelColumn
from .models.library_model import CollectionItem, CollectionUrlItem, FolderItem, LibraryModel
from .models.sync_action_combobox_model import SyncActionComboboxModel
from .threads import ThreadingWorker
from musicsync.music_sync_library import ExternalMetadataTable, TrackSyncAction, TrackSyncStatus, CollectionUrl, \
    Collection


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
        self.treeView.setModel(LibraryModel())
        self.treeView.expandAll()

        self.treeView.selectionModel().selectionChanged.connect(self.tree_selection_changed)
        self.treeView.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.treeView.customContextMenuRequested.connect(lambda point: TreeContextMenu(self.treeView, point))


        # File sync status page
        self.compare_button.pressed.connect(self.compare_collection)


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
            box.highlighted[int].connect(lambda index, box=box: self.statusbar.showMessage(box.itemData(index, Qt.ItemDataRole.StatusTipRole) or ''))
            box.view().viewport().installEventFilter(self)

        self.settings_filename_format_label.mousePressEvent = self.open_doc_url

        self.thread_pool = QThreadPool()


    @staticmethod
    def open_doc_url(*_):
        if QApplication.keyboardModifiers() == QtCore.Qt.KeyboardModifier.ControlModifier:
            QDesktopServices.openUrl(QUrl('https://github.com/yt-dlp/yt-dlp/tree/master?tab=readme-ov-file#output-template'))


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
            self.settings_url_name_format.setText(selected_collection.url_name_format)
            self.settings_exclude_urls_checkbox.setChecked(selected_collection.exclude_after_download)

            self.update_current_sync_folder(selected_collection.sync_bookmark_file, selected_collection.sync_bookmark_path, selected_collection.sync_bookmark_title_as_url_name)

            for box, status in self.action_combo_boxes.items():
                box.setCurrentIndex(box.findText(selected_collection.sync_actions[status].gui_string))

            self.update_metadata_suggestions_label()
            self.update_tags_label()
            self.update_sync_status_table()

            self.sync_stack.setCurrentIndex(1)
            self.metadata_stack.setCurrentIndex(1)
            self.tags_stack.setCurrentIndex(1)
            self.settings_stack.setCurrentIndex(1)
        else:
            self.sync_stack.setCurrentIndex(0)
            self.metadata_stack.setCurrentIndex(0)
            self.tags_stack.setCurrentIndex(0)
            self.settings_stack.setCurrentIndex(0)

        self.statusbar.clearMessage()

    def save_settings(self, item: CollectionItem | None = None):
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
        item.url_name_format = self.settings_url_name_format.text()
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

    def update_current_sync_folder(self, file: str, path: list[Collection.PathComponent] | None=None, set_url_name=False):
        if path is None:
            path = []

        current_collection = self.get_selected_collection()
        current_collection.sync_bookmark_file = file
        current_collection.sync_bookmark_path = path or []
        current_collection.sync_bookmark_title_as_url_name = set_url_name

        if file:
            font = self.settings_folder_path.font()
            font.setItalic(False)
            self.settings_bookmark_label.setFont(font)

            text = f'File: {file}\nFolder: {"/".join([e[1] for e in path])}'
            self.settings_bookmark_label.setText(text)
        else:
            font = self.settings_folder_path.font()
            font.setItalic(True)
            self.settings_bookmark_label.setFont(font)

            self.settings_bookmark_label.setText('Not syncing')

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
                folder.append(Collection.PathComponent(id=item.text(3), name=item.text(0)))
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

    def compare_finished(self, result: tuple):
        error, extra = result

        if error is None:
            selected_collection: CollectionItem = extra['selected_collection']
            selected_collection_xml: Collection = extra['selected_collection_xml']

            old_urls: dict[str, CollectionUrlItem] = {selected_collection.child(i).url: selected_collection.child(i) for
                                                      i in range(selected_collection.rowCount())}
            new_urls: dict[str, CollectionUrl] = {u.url: u for u in selected_collection_xml.urls}

            rows_to_be_removed = []
            for i, (old_url, item) in enumerate(old_urls.items()):
                if old_url in new_urls:
                    item.update(new_urls[old_url])
                else:
                    rows_to_be_removed.append(i)

                    folder = Collection.get_real_path(selected_collection, item)
                    delete = QMessageBox.question(self,
                                                  'Delete files',
                                                  f'The URL {item.text()} has been deleted from the bookmark folder. Do you want to delete the corresponding files located at {folder}?',
                                                  QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
                    if delete == QMessageBox.StandardButton.Yes:
                        for track in item.tracks.values():
                            path = Collection.get_real_path(selected_collection, item, track)
                            if os.path.isfile(path):
                                os.remove(path)

            for i in sorted(rows_to_be_removed, reverse=True):
                selected_collection.removeRow(i)

            for new_url, item in new_urls.items():
                if new_url not in old_urls:
                    selected_collection.appendRow(CollectionUrlItem.from_xml_object(item))

            self.update_sync_status_table()
        else:
            if isinstance(error, pd.errors.DatabaseError):
                QMessageBox.warning(self, 'Error', 'Bookmark sync could not be performed because the database is locked. Close your browser and try again.')
            else:
                QMessageBox.warning(self, 'Error', 'There were errors while comparing this collection')

        self.compare_button.setEnabled(True)

    def compare_collection(self):
        self.compare_button.setEnabled(False)
        selected_collection = self.get_selected_collection()
        selected_collection_xml = selected_collection.to_xml_object()

        worker = ThreadingWorker(selected_collection_xml.update_sync_status, extra={'selected_collection': selected_collection,
                                                                                    'selected_collection_xml': selected_collection_xml})
        # worker.result.connect(lambda _, s=selected_collection, x=selected_collection_xml: self.compare_finished(s, x))
        worker.signals.result.connect(self.compare_finished)
        self.thread_pool.start(worker)

    def update_sync_status_table(self):
        self.sync_status_table.setModel(FileSyncModel(self.get_selected_collection(), parent=self))
        self.sync_status_table.setItemDelegateForColumn(FileSyncModelColumn.ACTION, ActionComboboxDelegate(update_callback=self.sync_actions_updated, parent=self))
        for row in range(self.sync_status_table.model().rowCount()):
            self.sync_status_table.openPersistentEditor(self.sync_status_table.model().index(row, FileSyncModelColumn.ACTION))
        self.sync_status_table.resizeColumnsToContents()
        self.sync_actions_updated('')

    def sync_actions_updated(self, text):
        if text == TrackSyncAction.DECIDE_INDIVIDUALLY.gui_string or TrackSyncAction.DECIDE_INDIVIDUALLY in list(self.sync_status_table.model().df['action']):
            self.sync_button.setEnabled(False)
            self.sync_button.setStatusTip('All "Decide individually" actions have to be resolved before sync can start')
        else:
            self.sync_button.setEnabled(True)
            self.sync_button.setStatusTip('')

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
            if self.item.sync_bookmark_file:
                add_url_action.setToolTip('This collection is synchronized with a bookmarks folder, so manually adding URLs is not possible')
                add_url_action.setEnabled(False)

            self.addAction(add_url_action)

            import_urls_from_bookmarks_action = QAction('Import URLs From Bookmarks')
            import_urls_from_bookmarks_action.triggered.connect(self.import_from_bookmarks)
            if self.item.sync_bookmark_file:
                import_urls_from_bookmarks_action.setToolTip('This collection is synchronized with a bookmarks folder, so manually adding URLs is not possible')
                import_urls_from_bookmarks_action.setEnabled(False)
            self.addAction(import_urls_from_bookmarks_action)
        elif isinstance(self.item, CollectionUrlItem):
            exclude_action = QAction('Exclude URL from downloading', checkable=True, checked=self.item.excluded)
            exclude_action.triggered.connect(self.toggle_excluded)
            self.addAction(exclude_action)

            concat_action = QAction('Concatenate videos of playlist', checkable=True, checked=self.item.concat)
            concat_action.triggered.connect(self.toggle_concat)
            self.addAction(concat_action)

        if self.index.model() is not None:
            delete_action = QAction('Delete')
            delete_action.setIcon(QIcon.fromTheme(QIcon.ThemeIcon.EditDelete))
            delete_action.triggered.connect(self.remove)

            if isinstance(self.item, CollectionUrlItem) and self.item.parent().sync_bookmark_file:
                delete_action.setToolTip('This collection is synchronized with a bookmarks folder, so manually deleting URLs is not possible')
                delete_action.setEnabled(False)

            self.addAction(delete_action)

        self.setToolTipsVisible(True)
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
            self.model.add_url(parent=self.item, url=url)

    def import_from_bookmarks(self):
        bookmark_window = BookmarkDialog(self.parent)
        if bookmark_window.exec():
            urls = []

            def add_urls(tree_widget_item: QTreeWidgetItem, recursion_depth=None):
                if tree_widget_item.childCount() > 0 and (recursion_depth is None or recursion_depth > 0):
                    for i in range(tree_widget_item.childCount()):
                        add_urls(tree_widget_item.child(i), None if recursion_depth is None else recursion_depth - 1)
                elif tree_widget_item.text(2):
                    data = {'url': tree_widget_item.text(2)}
                    if bookmark_window.bookmark_title_check_box.isChecked():
                        data['name'] = tree_widget_item.text(0)

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

    def toggle_concat(self):
        self.item.concat = not self.item.concat