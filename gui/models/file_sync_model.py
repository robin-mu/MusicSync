from enum import IntEnum

import pandas as pd
from PySide6 import QtCore
from PySide6.QtCore import QModelIndex
from PySide6.QtWidgets import QComboBox

from musicsync.music_sync_library import TrackSyncAction, TrackSyncStatus
from .data_frame_model import DataFrameTableModel
from .item_delegates import ComboBoxDelegate
from .library_model import CollectionItem


class FileSyncModelColumn(IntEnum):
    URL_NAME = 0
    PLAYLIST_INDEX = 1
    TITLE = 2
    FILENAME = 3
    STATUS = 4
    ACTION = 5

    # internal columns
    COLLECTION_URL = 6
    URL = 7
    OCCURRENCE_INDEX = 8


    def __str__(self):
        if self == FileSyncModelColumn.URL_NAME:
            return 'URL Name'
        elif self == FileSyncModelColumn.FILENAME:
            return 'Filename'
        elif self == FileSyncModelColumn.TITLE:
            return 'Video Title'
        elif self == FileSyncModelColumn.STATUS:
            return 'Status'
        elif self == FileSyncModelColumn.ACTION:
            return 'Action'
        elif self == FileSyncModelColumn.COLLECTION_URL:
            return 'Collection URL Object'
        elif self == FileSyncModelColumn.PLAYLIST_INDEX:
            return 'Playlist Index'
        return None

    @property
    def df_column_name(self):
        if self == FileSyncModelColumn.URL_NAME:
            return 'url_name'
        elif self == FileSyncModelColumn.FILENAME:
            return 'filename'
        elif self == FileSyncModelColumn.TITLE:
            return 'title'
        elif self == FileSyncModelColumn.STATUS:
            return 'status'
        elif self == FileSyncModelColumn.ACTION:
            return 'action'
        elif self == FileSyncModelColumn.COLLECTION_URL:
            return 'collection_url'
        elif self == FileSyncModelColumn.PLAYLIST_INDEX:
            return 'playlist_index'
        elif self == FileSyncModelColumn.URL:
            return 'url'
        elif self == FileSyncModelColumn.OCCURRENCE_INDEX:
            return 'occurrence_index'
        return None


class FileSyncModel(DataFrameTableModel):
    def __init__(self, collection_item: CollectionItem, parent):
        if collection_item.compare_result is None:
            df = FileSyncModel.urls_to_df(collection_item)
            df.sort_values(by='status',
                           inplace=True,
                           kind='mergesort',
                           key=lambda col: col.apply(lambda s: s.sort_key))
        else:
            df = FileSyncModel.compare_result_to_df(collection_item)

        super().__init__(df, parent)

    def internal_columns(self) -> int:
        return len([FileSyncModelColumn.COLLECTION_URL, FileSyncModelColumn.URL,
                    FileSyncModelColumn.OCCURRENCE_INDEX])

    def delegate_columns(self) -> list[int]:
        return [FileSyncModelColumn.ACTION]

    def editable_columns(self) -> list[int]:
        return [FileSyncModelColumn.ACTION]

    def fillable_columns(self) -> list[int]:
        return [FileSyncModelColumn.ACTION]

    def column_display_name(self, col: int) -> str | None:
        return str(FileSyncModelColumn(col))

    def display_data(self, value) -> str:
        if isinstance(value, (TrackSyncStatus, TrackSyncAction)):
            return value.gui_string

        return super().display_data(value)

    @staticmethod
    def urls_to_df(collection_item: CollectionItem) -> pd.DataFrame:
        columns = [c.df_column_name for c in FileSyncModelColumn.__members__.values()]

        df = pd.DataFrame(columns=columns)
        for url in collection_item.urls:
            url_df = pd.DataFrame.from_records([dict(zip(columns, [
                url.name,
                track.playlist_index,
                track.title,
                track.filename,
                track.status,
                collection_item.sync_actions[track.status],
                url,
                track.url,
                track.occurrence_index
            ])) for track in url.tracks.itertuples()])

            df = pd.concat([df, url_df])

        return df

    @staticmethod
    def compare_result_to_df(collection_item: CollectionItem) -> pd.DataFrame:
        compare_result = collection_item.compare_result
        assert compare_result is not None  # make ide happy

        columns = [c.df_column_name for c in FileSyncModelColumn.__members__.values()]

        return pd.DataFrame(dict(zip(columns, [
            compare_result['collection_url'].apply(lambda x: x.name),
            compare_result['playlist_index'].fillna(''),
            compare_result['title'],
            compare_result['filename'],
            compare_result['status'],
            compare_result['status'].apply(lambda x: collection_item.sync_actions[x]),
            compare_result['collection_url'],
            compare_result['url'],
            compare_result['occurrence_index']
        ])))

class ActionComboboxDelegate(ComboBoxDelegate):
    def __init__(self, update_callback=None, window=None, view=None):
        ComboBoxDelegate.__init__(self, update_callback=update_callback, window=window, view=view)

    def to_model_data(self, val: str) -> TrackSyncAction:
        return next(a for a in TrackSyncAction.__members__.values() if a.gui_string == val)

    def get_combobox_items(self, index: QModelIndex) -> list[str]:
        status_index = index.model().index(index.row(), FileSyncModelColumn.STATUS)
        status = index.model().data(status_index, role=QtCore.Qt.ItemDataRole.BackgroundRole)

        return [a.gui_string for a in TrackSyncStatus.ACTION_OPTIONS[status]]

    def get_combobox_selection(self, index) -> str:
        return index.model().data(index, role=QtCore.Qt.ItemDataRole.BackgroundRole).gui_string

    def get_status_bar_text(self, index, box: QComboBox) -> str:
        return next(a for a in TrackSyncAction.__members__.values() if a.gui_string == box.itemText(index)).gui_status_tip
