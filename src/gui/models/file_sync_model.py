from enum import IntEnum

import pandas as pd
from PySide6 import QtCore
from PySide6.QtCore import QModelIndex
from PySide6.QtWidgets import QComboBox

from src.gui.models.data_frame_model import DataFrameTableModel
from src.gui.models.item_delegates import ComboBoxDelegate
from src.music_sync_library import TrackSyncStatus, TrackSyncAction


class FileSyncModelColumn(IntEnum):
    COLLECTION = 0
    URL_NAME = 1
    PLAYLIST_INDEX = 2
    FILE_PATH = 3
    TRACK_TITLE = 4
    STATUS = 5
    ACTION = 6

    def __str__(self):
        if self == FileSyncModelColumn.COLLECTION:
            return 'Collection'
        elif self == FileSyncModelColumn.URL_NAME:
            return 'URL Name'
        elif self == FileSyncModelColumn.PLAYLIST_INDEX:
            return 'Playlist Index'
        elif self == FileSyncModelColumn.FILE_PATH:
            return 'File Path'
        elif self == FileSyncModelColumn.TRACK_TITLE:
            return 'Track Title'
        elif self == FileSyncModelColumn.STATUS:
            return 'Status'
        elif self == FileSyncModelColumn.ACTION:
            return 'Action'
        return None


class FileSyncModel(DataFrameTableModel):
    def __init__(self, df: pd.DataFrame, parent):
        df.sort_values(by='status',
                       inplace=True,
                       kind='mergesort',
                       key=lambda col: col.apply(lambda s: s.sort_key))

        DataFrameTableModel.__init__(self, df, parent)

    def delegate_columns(self) -> list[int]:
        return [FileSyncModelColumn.ACTION]

    def column_display_name(self, col: int) -> str | None:
        return str(FileSyncModelColumn(col))

    def display_data(self, value) -> str:
        if isinstance(value, TrackSyncStatus):
            return value.gui_string

        return super().display_data(value)

class ActionComboboxDelegate(ComboBoxDelegate):
    def __init__(self, update_callback=None, parent=None):
        ComboBoxDelegate.__init__(self, update_callback=update_callback, parent=parent)

    def to_model_data(self, val: str) -> TrackSyncAction:
        return [a for a in TrackSyncAction.__members__.values() if a.gui_string == val][0]

    def get_combobox_items(self, index: QModelIndex) -> list[str]:
        status_index = index.model().index(index.row(), FileSyncModelColumn.STATUS)
        status = index.model().data(status_index, role=QtCore.Qt.ItemDataRole.BackgroundRole)

        return [a.gui_string for a in TrackSyncStatus.action_options()[status]]

    def get_combobox_selection(self, index) -> str:
        return index.model().data(index, role=QtCore.Qt.ItemDataRole.BackgroundRole).gui_string

    def get_status_bar_text(self, index, box: QComboBox) -> str:
        return [a for a in TrackSyncAction.__members__.values() if a.gui_string == box.itemText(index)][0].gui_status_tip
