import functools
from copy import deepcopy
from typing import cast

import pandas as pd
from PySide6 import QtWidgets
from PySide6.QtCore import QEvent, QItemSelection, Qt, QThread, QItemSelectionModel, QSignalBlocker, QPoint
from PySide6.QtGui import QAction, QCloseEvent, QIcon
from PySide6.QtWidgets import (
    QDialogButtonBox,
    QFileDialog,
    QMainWindow,
    QMenu,
    QMessageBox,
    QTreeView,
    QTreeWidget,
    QTreeWidgetItem, QHeaderView, )

from musicsync.music_sync_library import TrackSyncAction, TrackSyncStatus, Script, PathComponent, \
    ScriptReference
from musicsync.scripting.script_types import MetadataSuggestionsScript, DownloadScript
from .bookmark_dialog import BookmarkDialog
from .main_gui import Ui_MainWindow
from .models.file_sync_model import ActionComboboxDelegate, FileSyncModel, FileSyncModelColumn
from .models.gui_combobox_model import ActionComboboxItemModel, DownloadScriptComboboxItemModel
from .models.library_model import CollectionItem, CollectionUrlItem, FolderItem, LibraryModel
from .models.scripts_model import ScriptsModel, ScriptItem
from .threads import ThreadingWorker


class MainWindow(QMainWindow, Ui_MainWindow):
    def __init__(self):
        super(MainWindow, self).__init__()
        self.setupUi(self)

        # Menu bar
        self.action_new_library.triggered.connect(self.new_library)
        self.action_open_library.triggered.connect(self.open_library)
        self.action_save_library.triggered.connect(self.save_library)
        self.action_save_library_as.triggered.connect(self.save_library_as)

        # Library Tree View
        self.library_tree_view.setModel(LibraryModel('a.pkl'))
        self.library_tree_view.expandAll()

        self.library_tree_view.selectionModel().selectionChanged.connect(self.tree_selection_changed)
        self.library_tree_view.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.library_tree_view.customContextMenuRequested.connect(lambda point: TreeContextMenu(self.library_tree_view, point))

        self.tab_widget.currentChanged.connect(self.tab_changed)

        # File sync tab
        self.sync_status_table.setItemDelegateForColumn(FileSyncModelColumn.ACTION, ActionComboboxDelegate(
            update_callback=self.update_sync_buttons, window=self, view=self.sync_status_table))

        self.compare_button.pressed.connect(self.compare_collection)
        self.sync_button.pressed.connect(self.sync_collection)

        self.update_sync_buttons()

        # Collection settings tab
        self.settings_path_browse.pressed.connect(self.browse_folder_path)
        self.settings_sync_button.pressed.connect(self.change_sync_folder)
        self.settings_stop_sync_button.pressed.connect(lambda: self.update_current_sync_folder(''))

        self.action_combo_boxes = dict(
            zip([self.added_combo_box, self.not_downloaded_combo_box, self.removed_combo_box, self.local_combo_box,
                 self.permanent_combo_box, self.downloaded_combo_box],
                [TrackSyncStatus.ADDED_TO_SOURCE, TrackSyncStatus.NOT_DOWNLOADED, TrackSyncStatus.REMOVED_FROM_SOURCE,
                 TrackSyncStatus.LOCAL_FILE, TrackSyncStatus.PERMANENTLY_DOWNLOADED, TrackSyncStatus.DOWNLOADED]))
        for box, status in self.action_combo_boxes.items():
            box.setModel(ActionComboboxItemModel(status))
            box.highlighted.connect(lambda index, bx=box: self.statusbar.showMessage(
                bx.itemData(index, Qt.ItemDataRole.StatusTipRole) or ''))
            box.view().viewport().installEventFilter(self)

        # Scripting tab
        self.scripts_table.setModel(ScriptsModel(deepcopy(self.library_tree_view.model().scripts), window=self))
        self.scripts_table.header().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.scripts_table.expandAll()
        self.scripts_table.selectionModel().selectionChanged.connect(self.script_selection_changed)
        self.scripts_table.itemDelegate().closeEditor.connect(self.check_script_name)

        self.script_add_button.pressed.connect(self.add_script)
        self.script_remove_button.pressed.connect(self.remove_script)
        self.script_up_button.pressed.connect(functools.partial(self.move_script, direction=-1))
        self.script_down_button.pressed.connect(functools.partial(self.move_script, direction=1))

        self.when_combo_box.setModel(DownloadScriptComboboxItemModel())
        self.when_combo_box.highlighted.connect(lambda index: self.statusbar.showMessage(
            self.when_combo_box.itemData(index, Qt.ItemDataRole.StatusTipRole) or ''))
        self.when_combo_box.view().viewport().installEventFilter(self)

        self.threads: list[QThread] = []
        self.workers: list[ThreadingWorker] = []

        self.showMaximized()

    # --------
    # Menu bar
    # --------
    def new_library(self):
        if self.library_tree_view.model().has_changed():
            answer = QMessageBox.question(self, 'Save File',
                                          'The current file has not been saved yet. Do you want to save it?',
                                          QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No | QMessageBox.StandardButton.Cancel)

            if answer == QMessageBox.StandardButton.Yes:
                if not self.save_library():
                    return
            elif answer == QMessageBox.StandardButton.Cancel:
                return

        self.library_tree_view.setModel(LibraryModel())
        self.library_tree_view.selectionModel().selectionChanged.connect(self.tree_selection_changed)
        self.update_sync_buttons()
        self.update_sync_stack()

    def open_library(self):
        if self.library_tree_view.model().has_changed():
            answer = QMessageBox.question(self, 'Save Library',
                                          'The current library has not been saved yet. Do you want to save it?',
                                          QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No | QMessageBox.StandardButton.Cancel)

            if answer == QMessageBox.StandardButton.Yes:
                if not self.save_library():
                    return
            elif answer == QMessageBox.StandardButton.Cancel:
                return

        filename, ok = QFileDialog.getOpenFileName(self, 'Select a file to load', filter="Pickle files (*.pkl) (*.pkl)")
        if filename:
            self.library_tree_view.setModel(LibraryModel(filename))
            self.library_tree_view.selectionModel().selectionChanged.connect(self.tree_selection_changed)
            self.library_tree_view.expandAll()
            self.update_sync_buttons()
            self.update_sync_stack()

    def save_library(self):
        self.save_settings()
        if self.library_tree_view.model().path:
            self.library_tree_view.model().to_pickle()
            self.library_tree_view.model().to_xml()
            return True

        return self.save_library_as()

    def save_library_as(self):
        filename, ok = QFileDialog.getSaveFileName(self, 'Select a file to save to', filter="Pickle files (*.pkl) (*.pkl)")
        if filename:
            if not filename.endswith('.pkl'):
                filename += '.pkl'

            self.library_tree_view.model().to_pickle(filename)
            self.library_tree_view.model().to_xml(filename)
            self.library_tree_view.model().path = filename
            return True
        return False

    def tab_changed(self, *_):
        self.save_settings(self.get_selected_collection())

    def get_selected_collection(self) -> CollectionItem | None:
        selected_indexes = self.library_tree_view.selectedIndexes()
        if not selected_indexes:
            return None

        current_collection = self.library_tree_view.model().itemFromIndex(selected_indexes[0])
        if isinstance(current_collection, FolderItem):
            return None

        if isinstance(current_collection, CollectionUrlItem):
            current_collection = current_collection.parent()
        return current_collection

    # -----------------
    # Library tree view
    # -----------------
    def tree_selection_changed(self, selected: QItemSelection, deselected: QItemSelection):
        if not selected.indexes():
            return

        selected_collection = self.library_tree_view.model().itemFromIndex(selected.indexes()[0])

        if isinstance(selected_collection, CollectionUrlItem):
            selected_collection = selected_collection.parent()

        if deselected.indexes():
            deselected_collection = self.library_tree_view.model().itemFromIndex(deselected.indexes()[0])
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
            self.settings_subfolder_checkbox.setChecked(selected_collection.save_playlists_to_subfolders)
            self.settings_url_name_format.setText(selected_collection.url_name_format)
            self.settings_exclude_urls_checkbox.setChecked(selected_collection.exclude_after_download)
            self.settings_auto_concat_checkbox.setChecked(selected_collection.auto_concat_urls)
            self.settings_excluded_yt_dlp_fields.setText(selected_collection.excluded_yt_dlp_fields)
            self.settings_yt_dlp_options.setText(selected_collection.yt_dlp_options)

            self.update_current_sync_folder(selected_collection.sync_bookmark_file,
                                            selected_collection.sync_bookmark_path,
                                            selected_collection.sync_bookmark_title_as_url_name,
                                            selected_collection.sync_delete_files)

            for box, status in self.action_combo_boxes.items():
                box.setCurrentIndex(box.findText(selected_collection.sync_actions[status].gui_string))

            self.update_tables()
            self.update_sync_buttons()
            self.update_sync_stack()

            self.sync_stack.setCurrentIndex(1)
            self.metadata_stack.setCurrentIndex(1)
            self.tags_stack.setCurrentIndex(1)
            self.settings_stack.setCurrentIndex(1)
            self.scripting_stack.setCurrentIndex(1)
        else:
            self.sync_stack.setCurrentIndex(0)
            self.metadata_stack.setCurrentIndex(0)
            self.tags_stack.setCurrentIndex(0)
            self.settings_stack.setCurrentIndex(0)
            self.scripting_stack.setCurrentIndex(0)

        self.statusbar.clearMessage()

    def save_settings(self, item: CollectionItem | None = None):
        if item is None:
            item = self.get_selected_collection()
        if item is None:
            return

        item.folder_path = self.settings_folder_path.text()
        item.filename_format = self.settings_filename_format.text()
        item.file_extension = self.settings_file_extension.text()
        item.save_playlists_to_subfolders = self.settings_subfolder_checkbox.isChecked()
        item.url_name_format = self.settings_url_name_format.text()
        item.exclude_after_download = self.settings_exclude_urls_checkbox.isChecked()
        item.auto_concat_urls = self.settings_auto_concat_checkbox.isChecked()
        item.excluded_yt_dlp_fields = self.settings_excluded_yt_dlp_fields.text()
        item.yt_dlp_options = self.settings_yt_dlp_options.text()

        item.sync_bookmark_title_as_url_name = self.settings_bookmark_title_as_url_name_checkbox.isChecked()
        item.sync_delete_files = self.settings_bookmark_delete_files_checkbox.isChecked()

        item.sync_actions = {
            TrackSyncStatus.ADDED_TO_SOURCE: self.added_combo_box.model().invisibleRootItem().child(
                self.added_combo_box.currentIndex()).member,
            TrackSyncStatus.NOT_DOWNLOADED: self.not_downloaded_combo_box.model().invisibleRootItem().child(
                self.not_downloaded_combo_box.currentIndex()).member,
            TrackSyncStatus.REMOVED_FROM_SOURCE: self.removed_combo_box.model().invisibleRootItem().child(
                self.removed_combo_box.currentIndex()).member,
            TrackSyncStatus.LOCAL_FILE: self.local_combo_box.model().invisibleRootItem().child(
                self.local_combo_box.currentIndex()).member,
            TrackSyncStatus.PERMANENTLY_DOWNLOADED: self.permanent_combo_box.model().invisibleRootItem().child(
                self.permanent_combo_box.currentIndex()).member,
            TrackSyncStatus.DOWNLOADED: self.downloaded_combo_box.model().invisibleRootItem().child(
                self.downloaded_combo_box.currentIndex()).member,
        }

        item.script_settings = [ScriptReference(it.script.name, it.checkState() == Qt.CheckState.Checked, it.row()) for it in self.scripts_table.model().items]

        self.save_script()
        self.library_tree_view.model().scripts = deepcopy(self.scripts_table.model().scripts)

    def update_tables(self):
        current_collection = self.get_selected_collection()
        if current_collection is None:
            return

        self.sync_status_table.setModel(FileSyncModel(current_collection, parent=self))

        self.sync_status_table.horizontalHeader().setSectionResizeMode(FileSyncModelColumn.ACTION, QtWidgets.QHeaderView.ResizeMode.ResizeToContents)
        for col in FileSyncModelColumn.__members__.values():
            if col != FileSyncModelColumn.ACTION:
                self.sync_status_table.horizontalHeader().setSectionResizeMode(col, QtWidgets.QHeaderView.ResizeMode.Stretch)
        self.update_sync_buttons()

        # Scripts table
        self.scripts_table.model().update_table(current_collection.script_settings)

    # -------------
    # File sync tab
    # -------------
    def compare_collection(self):
        selected_collection = self.get_selected_collection()
        assert selected_collection is not None

        selected_collection.comparing = True

        thread = QThread()
        worker = ThreadingWorker(selected_collection.compare,
                                 extra={'selected_collection': selected_collection})
        worker.moveToThread(thread)
        thread.started.connect(worker.run)
        worker.result.connect(thread.quit)
        worker.result.connect(worker.deleteLater)
        worker.result.connect(self.compare_finished)
        worker.progress.connect(functools.partial(self.update_sync_progress, collection=selected_collection))
        thread.finished.connect(thread.deleteLater)
        worker.result.connect(lambda *_, w=worker: self.workers.remove(w))
        thread.finished.connect(lambda *_, t=thread: self.threads.remove(t))

        thread.start()

        self.threads.append(thread)
        self.workers.append(worker)

        self.update_sync_buttons()
        self.update_sync_stack()

    def compare_finished(self, result, extra):
        selected_collection: CollectionItem = extra['selected_collection']

        if not isinstance(result, Exception):
            print(result[['url', 'occurrence_index']])

            selected_collection.compare_result = result

            self.update_tables()
        else:
            if isinstance(result, pd.errors.DatabaseError):
                QMessageBox.warning(self, 'Error',
                                    'Bookmark sync could not be performed because the database is locked. Close your browser and try again.')
            elif isinstance(result, InterruptedError):
                return
            else:
                QMessageBox.warning(self, 'Error', f'There was an error while comparing this collection: {result}')

        selected_collection.comparing = False
        self.update_sync_buttons()
        self.update_sync_stack()

    def sync_collection(self):
        selected_collection = self.get_selected_collection()
        assert selected_collection is not None  # make ide happy

        selected_collection.syncing = True

        thread = QThread()
        worker = ThreadingWorker(selected_collection.sync,
                                 self.sync_status_table.model().df,
                                 extra={'selected_collection': selected_collection})
        worker.moveToThread(thread)
        thread.started.connect(worker.run)
        worker.result.connect(thread.quit)
        worker.result.connect(worker.deleteLater)
        worker.result.connect(self.sync_finished)
        worker.progress.connect(functools.partial(self.update_sync_progress, collection=selected_collection))
        thread.finished.connect(thread.deleteLater)
        worker.result.connect(lambda *_, w=worker: self.workers.remove(w))
        thread.finished.connect(lambda *_, t=thread: self.threads.remove(t))

        thread.start()

        self.threads.append(thread)
        self.workers.append(worker)

        self.update_sync_buttons()
        self.update_sync_stack()

    def sync_finished(self, result, extra):
        print(result, extra)
        extra['selected_collection'].syncing = False
        extra['selected_collection'].compare_result = None
        self.update_sync_buttons()
        self.update_sync_stack()

    def update_sync_buttons(self, last_selected_action: str = None):
        current_collection = self.get_selected_collection()
        if current_collection is None:
            self.compare_button.setEnabled(False)
            self.sync_button.setEnabled(False)
            return

        if current_collection.comparing or current_collection.syncing:
            self.compare_button.setEnabled(False)
            self.sync_button.setEnabled(False)
            return
        else:
            self.compare_button.setEnabled(True)

        if self.sync_status_table.model() is None or self.sync_status_table.model().rowCount() == 0:
            self.sync_button.setEnabled(False)
            self.sync_button.setStatusTip(
                'You need to fill the file sync table by comparing the current collection before sync can start.')
            return

        if last_selected_action == TrackSyncAction.DECIDE_INDIVIDUALLY.gui_string or TrackSyncAction.DECIDE_INDIVIDUALLY in list(
                self.sync_status_table.model().df['action']):
            self.sync_button.setEnabled(False)
            self.sync_button.setStatusTip(
                'All "Decide individually" actions have to be resolved before sync can start.')
        else:
            self.sync_button.setEnabled(True)
            self.sync_button.setStatusTip('Execute all selected sync actions.')

    def update_sync_stack(self):
        current_collection = self.get_selected_collection()
        if current_collection is None:
            return

        if current_collection.comparing or current_collection.syncing:
            self.sync_progress_bar.setValue(current_collection.sync_progress * self.sync_progress_bar.maximum())
            self.sync_progress_label.setText(current_collection.sync_text)
        else:
            self.sync_progress_bar.setValue(0)
            self.sync_progress_label.setText('')

    def update_sync_progress(self, progress: float = 0, text: str = '', collection: CollectionItem = None):
        collection.sync_progress = progress
        collection.sync_text = text
        self.update_sync_stack()

    # -----------------------
    # Collection settings tab
    # -----------------------
    def browse_folder_path(self):
        folder = QFileDialog.getExistingDirectory(self, 'Select a directory')
        if folder:
            self.settings_folder_path.setText(folder)

    def update_current_sync_folder(self, file: str, path: list[PathComponent] | None = None,
                                   set_url_name=False, delete=False):
        if path is None:
            path: list[PathComponent] = []

        current_collection = self.get_selected_collection()
        current_collection.sync_bookmark_file = file
        current_collection.sync_bookmark_path = path or []
        current_collection.sync_bookmark_title_as_url_name = set_url_name
        current_collection.sync_delete_files = delete

        self.settings_bookmark_title_as_url_name_checkbox.setChecked(set_url_name)
        self.settings_bookmark_delete_files_checkbox.setChecked(delete)

        if file:
            font = self.settings_bookmark_label.font()
            font.setItalic(False)
            self.settings_bookmark_label.setFont(font)

            text = f'File: {file}\nFolder: {"/".join([e[1] for e in path])}'
            self.settings_bookmark_label.setText(text)

            self.settings_bookmark_title_as_url_name_checkbox.setEnabled(True)
            self.settings_bookmark_delete_files_checkbox.setEnabled(True)
        else:
            self.settings_bookmark_label.setText('<html><head/><body><p><span style="font-style:normal">File: </span><span style=" font-style:italic;">Not syncing<br/></span><span style="font-style:normal">Folder: </span><span style=" font-style:italic;">Not syncing</span></p></body></html>')
            self.settings_bookmark_title_as_url_name_checkbox.setEnabled(False)
            self.settings_bookmark_delete_files_checkbox.setEnabled(False)

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
                folder.append(PathComponent(id=item.text(3), name=item.text(0)))
                idx = idx.parent()

            self.update_current_sync_folder(file, folder[::-1], bookmark_window.bookmark_title_check_box.isChecked())

    # -------------
    # Scripting tab
    # -------------
    def add_script(self):
        selection = self.scripts_table.selectedIndexes()
        if len(selection) == 0:
            return

        new_index = self.scripts_table.model().add_script(selection[0])

        self.scripts_table.selectionModel().select(new_index, QItemSelectionModel.SelectionFlag.ClearAndSelect | QItemSelectionModel.SelectionFlag.Rows)
        self.scripts_table.selectionModel().setCurrentIndex(new_index, QItemSelectionModel.SelectionFlag.ClearAndSelect | QItemSelectionModel.SelectionFlag.Rows)
        self.scripts_table.edit(new_index)

    def remove_script(self):
        selection = self.scripts_table.selectedIndexes()
        if len(selection) == 0:
            return

        self.scripts_table.model().remove_script(selection[0])

    def move_script(self, direction: int):
        selection = self.scripts_table.selectedIndexes()
        if len(selection) == 0:
            return

        idx = selection[0]
        parent_idx = idx.parent()
        if not parent_idx.isValid():
            return

        parent_item = self.scripts_table.model().itemFromIndex(parent_idx)
        row = idx.row()
        new_row = row + direction

        if new_row < 0 or new_row >= parent_item.rowCount():
            return

        taken = parent_item.takeRow(row)
        parent_item.insertRow(new_row, taken)

        new_index = self.scripts_table.model().index(new_row, idx.column(), parent_idx)
        self.scripts_table.setCurrentIndex(new_index)
        self.scripts_table.scrollTo(new_index)


    def save_script(self, selection: QItemSelection | None = None):
        if selection is None:
            index = self.scripts_table.selectedIndexes()
            if len(index) == 0:
                return

            item = self.scripts_table.model().itemFromIndex(index[0])
            if not isinstance(item, ScriptItem):
                return
        else:
            item = self.scripts_table.model().itemFromIndex(selection.indexes()[0])
            if not isinstance(item, ScriptItem):
                return

        script = item.script

        script.name = item.text()
        script.script = self.script_editor.toPlainText()

        if isinstance(script, MetadataSuggestionsScript):
            script.field_name = self.field_name_entry.text()
            script.timed_data = self.timed_field_checkbox.isChecked()
            script.show_format_options = self.format_options_group_box.isChecked()
            script.default_format_as_title = self.format_as_title_checkbox.isChecked()
            script.default_remove_brackets = self.remove_brackets_checkbox.isChecked()
            script.local_field = self.local_field_checkbox.isChecked()
            script.overwrite_metadata_table = self.overwrite_metadata_checkbox.isChecked()
        elif isinstance(script, DownloadScript):
            script.when = self.when_combo_box.model().invisibleRootItem().child(self.when_combo_box.currentIndex()).member


    def script_selection_changed(self, selected: QItemSelection, deselected: QItemSelection):
        if not deselected.isEmpty():
            self.save_script(deselected)

        if selected.isEmpty():
            return

        item = self.scripts_table.model().itemFromIndex(selected.indexes()[0])
        if not isinstance(item, ScriptItem):
            self.script_type_settings_stack.setCurrentIndex(0)
            return

        script: Script = item.script

        if isinstance(script, MetadataSuggestionsScript):
            self.script_type_settings_stack.setCurrentIndex(1)
            self.field_name_entry.setText(script.field_name)
            self.timed_field_checkbox.setChecked(script.timed_data)
            self.format_options_group_box.setChecked(script.show_format_options)
            self.format_as_title_checkbox.setChecked(script.default_format_as_title)
            self.remove_brackets_checkbox.setChecked(script.default_remove_brackets)
            self.local_field_checkbox.setChecked(script.local_field)
            self.overwrite_metadata_checkbox.setChecked(script.overwrite_metadata_table)
        elif isinstance(script, DownloadScript):
            with QSignalBlocker(self.when_combo_box):  # so that the "highlighted" signal is not emitted
                self.when_combo_box.setCurrentIndex(self.when_combo_box.findText(script.when.gui_string))
            self.script_type_settings_stack.setCurrentIndex(2)

        self.script_editor.setPlainText(script.script)

    def check_script_name(self, *_):
        idx = self.scripts_table.currentIndex()
        if not idx.isValid():
            return

        if not idx.parent().isValid():
            return

        item = self.scripts_table.model().itemFromIndex(idx)
        if not item.text().strip():
            item.setText("Script")

    def eventFilter(self, obj, event):
        et = event.type()

        # Sync action combo boxes
        for box in self.action_combo_boxes.keys():
            if obj is box.view().viewport() and et in (QEvent.Type.Leave, QEvent.Type.Hide):
                self.statusbar.clearMessage()

        # Download script when setting
        if obj is self.when_combo_box.view().viewport() and et in (QEvent.Type.Leave, QEvent.Type.Hide):
            self.statusbar.clearMessage()

        return super(MainWindow, self).eventFilter(obj, event)

    def closeEvent(self, event: QCloseEvent):
        self.save_settings()

        if self.library_tree_view.model().has_changed():
            answer = QMessageBox.question(self, 'Save Library',
                                          'The current library has not been saved yet. Do you want to save it?',
                                          QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No | QMessageBox.StandardButton.Cancel)

            if answer == QMessageBox.StandardButton.Yes:
                if self.save_library():
                    event.accept()
                else:
                    event.ignore()
                    return
            elif answer == QMessageBox.StandardButton.Cancel:
                event.ignore()
                return
            elif answer == QMessageBox.StandardButton.No:
                event.accept()

        if self.threads:
            answer = QMessageBox.question(self, 'Running Downloads',
                                          'There are downloads running. Do you still want to quit?',
                                          QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
            if answer == QMessageBox.StandardButton.No:
                event.ignore()
                return
            elif answer == QMessageBox.StandardButton.Yes:
                for thread in self.threads:
                    thread.requestInterruption()
                    thread.quit()
                    thread.wait(5000)


class TreeContextMenu(QMenu):
    def __init__(self, parent: QTreeView, point: QPoint):
        super().__init__(parent)
        self.parent = parent
        self.model: LibraryModel = cast(LibraryModel, parent.model())

        self.index = parent.indexAt(point)

        if self.index.model() is None:
            self.item = self.model.root
        else:
            self.item = self.model.itemFromIndex(self.index)

        if isinstance(self.item, FolderItem) or self.index.model() is None:
            add_folder_action = QAction('Add Folder')
            add_folder_action.setIcon(QIcon.fromTheme(QIcon.ThemeIcon.FolderNew))
            add_folder_action.triggered.connect(lambda: self.add_folder(is_folder=True))
            self.addAction(add_folder_action)

            add_collection_action = QAction('Add Collection')
            add_collection_action.setIcon(QIcon.fromTheme(QIcon.ThemeIcon.ContactNew))
            add_collection_action.triggered.connect(lambda: self.add_folder(is_folder=False))
            self.addAction(add_collection_action)
        elif isinstance(self.item, CollectionItem):
            add_url_action = QAction('Add URL')
            add_url_action.setIcon(QIcon.fromTheme('list-add'))
            add_url_action.triggered.connect(self.add_url)
            if self.item.sync_bookmark_file:
                add_url_action.setToolTip(
                    'This collection is synchronized with a bookmarks folder, so manually adding URLs is not possible')
                add_url_action.setEnabled(False)

            self.addAction(add_url_action)

            import_urls_from_bookmarks_action = QAction('Import URLs From Bookmarks')
            import_urls_from_bookmarks_action.triggered.connect(self.import_from_bookmarks)
            if self.item.sync_bookmark_file:
                import_urls_from_bookmarks_action.setToolTip(
                    'This collection is synchronized with a bookmarks folder, so manually adding URLs is not possible')
                import_urls_from_bookmarks_action.setEnabled(False)
            self.addAction(import_urls_from_bookmarks_action)
        elif isinstance(self.item, CollectionUrlItem):
            subfolder_action = QAction('Save playlist in subfolder', checkable=True, checked=self.item.save_to_subfolder)
            subfolder_action.triggered.connect(self.toggle_subfolder)
            self.addAction(subfolder_action)

            exclude_action = QAction('Exclude URL from downloading', checkable=True, checked=self.item.excluded)
            exclude_action.triggered.connect(self.toggle_excluded)
            self.addAction(exclude_action)

            concat_action = QAction('Concatenate tracks of playlist', checkable=True, checked=self.item.concat)
            concat_action.triggered.connect(self.toggle_concat)
            self.addAction(concat_action)

        if self.index.model() is not None:
            delete_action = QAction('Delete')
            delete_action.setIcon(QIcon.fromTheme(QIcon.ThemeIcon.EditDelete))
            delete_action.triggered.connect(self.remove)

            if isinstance(self.item, CollectionUrlItem) and self.item.parent().sync_bookmark_file:
                delete_action.setToolTip(
                    'This collection is synchronized with a bookmarks folder, so manually deleting URLs is not possible')
                delete_action.setEnabled(False)

            self.addAction(delete_action)

        self.setToolTipsVisible(True)
        self.exec(self.parent.mapToGlobal(point))

    def add_folder(self, is_folder: bool):
        # self.item is the parent item
        assert isinstance(self.item, FolderItem)  # make ide happy
        if is_folder:
            new_folder = self.model.add_folder(parent=self.item)
        else:
            new_folder = self.model.add_collection(parent=self.item)

        new_index = self.model.indexFromItem(new_folder)
        self.parent.setCurrentIndex(new_index)
        self.parent.edit(new_index)

    def remove(self):
        parent_index = self.index.parent()
        self.model.removeRow(self.index.row(), parent_index)

    def add_url(self):
        assert isinstance(self.item, CollectionItem)  # make ide happy

        new_url = self.model.add_url(parent=self.item)

        new_index = self.model.indexFromItem(new_url)
        self.parent.setCurrentIndex(new_index)
        self.parent.edit(new_index)

    def import_from_bookmarks(self):
        assert isinstance(self.item, CollectionItem)  # make ide happy

        bookmark_window = BookmarkDialog(self.parent)
        if bookmark_window.exec():
            urls = []

            def add_urls(tree_widget_item: QTreeWidgetItem, recursion_depth=None):
                if tree_widget_item.childCount() > 0 and (recursion_depth is None or recursion_depth > 0):
                    for i in range(tree_widget_item.childCount()):
                        add_urls(tree_widget_item.child(i), None if recursion_depth is None else recursion_depth - 1)
                elif tree_widget_item.text(2):
                    url = {'url': tree_widget_item.text(2)}
                    if bookmark_window.bookmark_title_check_box.isChecked():
                        url['name'] = tree_widget_item.text(0)

                    urls.append(url)

            for item in bookmark_window.bookmark_tree_widget.selectedItems():
                add_urls(item, recursion_depth=None if bookmark_window.subfolder_check_box.isChecked() else 1)

            for data in urls:
                self.model.add_url(self.item, **data)

    def toggle_excluded(self):
        assert isinstance(self.item, CollectionUrlItem)

        self.item.excluded = not self.item.excluded
        font = self.item.font()
        font.setStrikeOut(not font.strikeOut())
        self.item.setFont(font)

    def toggle_concat(self):
        assert isinstance(self.item, CollectionUrlItem)
        self.item.concat = not self.item.concat

    def toggle_subfolder(self):
        assert isinstance(self.item, CollectionUrlItem)
        self.item.save_to_subfolder = not self.item.save_to_subfolder
