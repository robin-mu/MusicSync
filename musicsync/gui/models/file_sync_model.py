from enum import IntEnum

import pandas as pd
from PySide6 import QtCore
from PySide6.QtCore import QModelIndex
from PySide6.QtWidgets import QComboBox

from .library_model import CollectionItem
from .data_frame_model import DataFrameTableModel
from .item_delegates import ComboBoxDelegate

from music_sync_library import Collection, TrackSyncAction, TrackSyncStatus


class FileSyncModelColumn(IntEnum):
    COLLECTION = 0
    URL_NAME = 1
    FILE_PATH = 2
    TRACK_TITLE = 3
    STATUS = 4
    ACTION = 5
    COLLECTION_URL = 6
    TRACK = 7

    def __str__(self):
        if self == FileSyncModelColumn.COLLECTION:
            return 'Collection'
        elif self == FileSyncModelColumn.URL_NAME:
            return 'URL Name'
        elif self == FileSyncModelColumn.FILE_PATH:
            return 'File Path'
        elif self == FileSyncModelColumn.TRACK_TITLE:
            return 'Track Title'
        elif self == FileSyncModelColumn.STATUS:
            return 'Status'
        elif self == FileSyncModelColumn.ACTION:
            return 'Action'
        elif self == FileSyncModelColumn.COLLECTION_URL:
            return 'Collection URL Object'
        elif self == FileSyncModelColumn.TRACK:
            return 'Track Object'
        return None


class FileSyncModel(DataFrameTableModel):
    def __init__(self, collection: CollectionItem, parent):
        df = FileSyncModel.collection_to_df(collection.to_xml_object())
        df.sort_values(by='status',
                       inplace=True,
                       kind='mergesort',
                       key=lambda col: col.apply(lambda s: s.sort_key))

        super().__init__(df, parent)

    def internal_columns(self) -> int:
        return len([FileSyncModelColumn.TRACK, FileSyncModelColumn.COLLECTION_URL])

    def delegate_columns(self) -> list[int]:
        return [FileSyncModelColumn.ACTION]

    def column_display_name(self, col: int) -> str | None:
        return str(FileSyncModelColumn(col))

    def display_data(self, value) -> str:
        if isinstance(value, TrackSyncStatus):
            return value.gui_string

        return super().display_data(value)

    @staticmethod
    def collection_to_df(collection: Collection) -> pd.DataFrame:
        df = pd.DataFrame(
            columns=['collection', 'url_name', 'file_path', 'track_title', 'status', 'action', 'collection_url',
                     'track'])
        for url in collection.urls:
            url_df = pd.DataFrame.from_records([{'collection': collection.name,
                                                 'url_name': url.name,
                                                 'file_path': track.path,
                                                 'track_title': track.title,
                                                 'status': track.status,
                                                 'action': collection.sync_actions[track.status],
                                                 'collection_url': url,
                                                 'track': track} for track in url.tracks.values()])

            df = pd.concat([df, url_df])

        return df

class ActionComboboxDelegate(ComboBoxDelegate):
    def __init__(self, update_callback=None, parent=None):
        ComboBoxDelegate.__init__(self, update_callback=update_callback, parent=parent)

    def to_model_data(self, val: str) -> TrackSyncAction:
        return next(a for a in TrackSyncAction.__members__.values() if a.gui_string == val)

    def get_combobox_items(self, index: QModelIndex) -> list[str]:
        status_index = index.model().index(index.row(), FileSyncModelColumn.STATUS)
        status = index.model().data(status_index, role=QtCore.Qt.ItemDataRole.BackgroundRole)

        return [a.gui_string for a in TrackSyncStatus.action_options()[status]]

    def get_combobox_selection(self, index) -> str:
        return index.model().data(index, role=QtCore.Qt.ItemDataRole.BackgroundRole).gui_string

    def get_status_bar_text(self, index, box: QComboBox) -> str:
        return next(a for a in TrackSyncAction.__members__.values() if a.gui_string == box.itemText(index)).gui_status_tip
