from typing import cast, Union, Callable

import pandas as pd
from PySide6.QtCore import QModelIndex
from PySide6.QtGui import QIcon

from musicsync.downloader import MusicSyncDownloader
from musicsync.music_sync_library import Collection, CollectionUrl, Folder, MusicSyncLibrary, Script, PathComponent, \
    TrackSyncStatus, TrackSyncAction, ScriptReference
from .xml_model import XmlObjectModel, XmlObjectModelItem


class LibraryModel(XmlObjectModel):
    def __init__(self, path: str=None):
        super(LibraryModel, self).__init__()

        self.saved_library_object: MusicSyncLibrary | None = None
        self.library_object: MusicSyncLibrary | None = None

        if path is not None:
            # self.loaded_library_object = MusicSyncLibrary.read_pickle(path)
            self.saved_library_object = MusicSyncLibrary.read_xml(path)  # only used to determine if library has been changed before saving
            self.library_object = MusicSyncLibrary.read_xml(path)  # has to be a copy, not the same object as saved_library_object

            assert self.library_object is not None  # make ide happy

            self.pull_from_xml_object()

    @property
    def path(self) -> str:
        assert self.library_object is not None  # make ide happy
        return self.library_object.path

    @path.setter
    def path(self, value: str):
        self.library_object.path = value

    @property
    def scripts(self) -> set['Script']:
        assert self.library_object is not None
        return self.library_object.scripts

    @scripts.setter
    def scripts(self, value: set['Script']):
        self.library_object.scripts = value

    @property
    def metadata_table(self) -> pd.DataFrame:
        assert self.library_object is not None
        return self.library_object.metadata_table

    @metadata_table.setter
    def metadata_table(self, value: pd.DataFrame):
        self.library_object.metadata_table = value

    # different name because children already is an attribute of QObject
    @property
    def children_library(self) -> list[Union['Folder', 'Collection']]:
        assert self.library_object is not None

        self.push_to_xml_object()
        return self.library_object.children

    @children_library.setter
    def children_library(self, value: list[Union['Folder', 'Collection']]):
        assert self.library_object is not None

        self.library_object.children = value
        self.pull_from_xml_object()

    def push_to_xml_object(self):
        children = []
        for i in range(self.root.row_count()):
            row = cast(XmlObjectModelItem, self.root.child(i))
            row.push_to_xml_object()
            children.append(row.xml_object)

        self.library_object.children = children

    def pull_from_xml_object(self) -> None:
        self.removeRows(0, self.rowCount())

        assert self.library_object is not None  # make ide happy

        for child in self.library_object.children:
            if isinstance(child, Folder):
                self.insert_item_at_item(FolderItem(child))
            elif isinstance(child, Collection):
                self.insert_item_at_item(CollectionItem(child))

    def item_is_container(self, item: XmlObjectModelItem) -> bool:
        if isinstance(item, CollectionUrlItem):
            return False

        return True

    def validate_move(self, source_parent: QModelIndex, source_row: int, destination_parent: QModelIndex, destination_child: int) -> bool:
        parent_item = self.item_from_index(destination_parent)
        item = self.item_from_index(source_parent).child(source_row)

        if (parent_item is None or isinstance(parent_item, FolderItem)) and isinstance(item, CollectionUrlItem):
            return False

        if isinstance(parent_item, CollectionItem) and (isinstance(item, (CollectionItem, FolderItem))):
            return False

        if isinstance(parent_item, CollectionUrlItem):
            return False

        return True

    def to_xml(self, filename: str | None=None):
        if filename is None:
            filename: str = self.path

        if filename.endswith('.pkl'):
            filename: str = filename[:-4] + '.xml'

        assert self.library_object is not None
        self.library_object.write_xml(filename)
        self.saved_library_object = MusicSyncLibrary.read_xml(filename)

    def to_pickle(self, filename: str | None=None):
        if filename is None:
            filename: str = self.path

        assert self.library_object is not None

        self.library_object.write_pickle(filename)
        self.saved_library_object = MusicSyncLibrary.read_pickle(filename)

    def has_changed(self):
        if self.root.row_count() == 0:
            return False

        if self.saved_library_object is None:
            return True

        return self.library_object != self.saved_library_object


    def add_folder(self, parent: FolderItem):
        new_folder = FolderItem()
        self.insert_item_at_item(new_folder, None, parent)
        return new_folder

    def add_collection(self, parent: FolderItem):
        new_collection = CollectionItem()
        self.insert_item_at_item(new_collection, None, parent)
        return new_collection

    def add_url(self, parent: CollectionItem, url: str='', name: str= ''):
        new_url = CollectionUrlItem(url=url, name=name, concat=parent.auto_concat_urls, resolved=False)
        self.insert_item_at_item(new_url, None, parent)
        return new_url


class FolderItem(XmlObjectModelItem):
    def __init__(self, xml_object: Folder | None = None, **kwargs):
        super().__init__(xml_object, icon=QIcon.fromTheme('folder'))
        if xml_object is None:
            self.xml_object = Folder(**kwargs)
        else:
            self.xml_object = xml_object

        self.pull_from_xml_object()

    @property
    def name(self) -> str:
        return self.xml_object.name

    @name.setter
    def name(self, value: str) -> None:
        self.xml_object.name = value

    @property
    def children(self) -> list[Union['Folder', 'Collection']]:
        self.push_to_xml_object()
        return self.xml_object.children

    @children.setter
    def children(self, value: list[Union['Folder', 'Collection']]):
        self.xml_object.children = value
        self.pull_from_xml_object()

    def get_text(self) -> str:
        return self.xml_object.name

    def set_text(self, value: str):
        self.xml_object.name = value

    def pull_from_xml_object(self):
        assert self.model is not None
        self.remove_rows(0, self.row_count())

        for child in self.xml_object.children:
            if isinstance(child, Folder):
                self.append_row(FolderItem(child))
            elif isinstance(child, Collection):
                self.append_row(CollectionItem(child))

    def push_to_xml_object(self):
        children = []
        for i in range(self.row_count()):
            child = self.child(i)
            child.push_to_xml_object()
            children.append(child.xml_object)

        self.xml_object.children = children


class CollectionItem(XmlObjectModelItem):
    def __init__(self, xml_object: Collection | None = None, **kwargs):
        super().__init__(xml_object, icon=QIcon.fromTheme('text-x-generic'))
        if xml_object is None:
            self.xml_object = Collection(**kwargs)
        else:
            self.xml_object = xml_object

        self.pull_from_xml_object()

        self.comparing: bool = False
        self.syncing: bool = False
        self.sync_progress: float = 0
        self.sync_text: str = ''
        self.compare_result: pd.DataFrame | None = None

    @property
    def name(self) -> str:
        return self.xml_object.name

    @name.setter
    def name(self, value: str) -> None:
        self.xml_object.name = value

    @property
    def folder_path(self) -> str:
        return self.xml_object.folder_path

    @folder_path.setter
    def folder_path(self, value: str) -> None:
        self.xml_object.folder_path = value

    @property
    def filename_format(self) -> str:
        return self.xml_object.filename_format

    @filename_format.setter
    def filename_format(self, value: str) -> None:
        self.xml_object.filename_format = value

    @property
    def file_extension(self) -> str:
        return self.xml_object.file_extension

    @file_extension.setter
    def file_extension(self, value: str) -> None:
        self.xml_object.file_extension = value

    @property
    def save_playlists_to_subfolders(self) -> bool:
        return self.xml_object.save_playlists_to_subfolders

    @save_playlists_to_subfolders.setter
    def save_playlists_to_subfolders(self, value: bool) -> None:
        self.xml_object.save_playlists_to_subfolders = value

    @property
    def url_name_format(self) -> str:
        return self.xml_object.url_name_format

    @url_name_format.setter
    def url_name_format(self, value: str) -> None:
        self.xml_object.url_name_format = value

    @property
    def exclude_after_download(self) -> bool:
        return self.xml_object.exclude_after_download

    @exclude_after_download.setter
    def exclude_after_download(self, value: bool) -> None:
        self.xml_object.exclude_after_download = value

    @property
    def auto_concat_urls(self) -> bool:
        return self.xml_object.auto_concat_urls

    @auto_concat_urls.setter
    def auto_concat_urls(self, value: bool) -> None:
        self.xml_object.auto_concat_urls = value

    @property
    def excluded_yt_dlp_fields(self) -> str:
        return self.xml_object.excluded_yt_dlp_fields

    @excluded_yt_dlp_fields.setter
    def excluded_yt_dlp_fields(self, value: str) -> None:
        self.xml_object.excluded_yt_dlp_fields = value

    @property
    def yt_dlp_options(self) -> str:
        return self.xml_object.yt_dlp_options

    @yt_dlp_options.setter
    def yt_dlp_options(self, value: str) -> None:
        self.xml_object.yt_dlp_options = value

    @property
    def sync_bookmark_file(self) -> str:
        return self.xml_object.sync_bookmark_file

    @sync_bookmark_file.setter
    def sync_bookmark_file(self, value: str) -> None:
        self.xml_object.sync_bookmark_file = value

    @property
    def sync_bookmark_path(self) -> list[PathComponent]:
        return self.xml_object.sync_bookmark_path

    @sync_bookmark_path.setter
    def sync_bookmark_path(self, value: list[PathComponent]) -> None:
        self.xml_object.sync_bookmark_path = value

    @property
    def sync_bookmark_title_as_url_name(self) -> bool:
        return self.xml_object.sync_bookmark_title_as_url_name

    @sync_bookmark_title_as_url_name.setter
    def sync_bookmark_title_as_url_name(self, value: bool) -> None:
        self.xml_object.sync_bookmark_title_as_url_name = value

    @property
    def sync_delete_files(self) -> bool:
        return self.xml_object.sync_delete_files

    @sync_delete_files.setter
    def sync_delete_files(self, value: bool) -> None:
        self.xml_object.sync_delete_files = value

    @property
    def sync_actions(self) -> dict[TrackSyncStatus, TrackSyncAction]:
        return self.xml_object.sync_actions

    @sync_actions.setter
    def sync_actions(self, value: dict[TrackSyncStatus, TrackSyncAction]) -> None:
        self.xml_object.sync_actions = value

    @property
    def script_settings(self) -> list[ScriptReference]:
        return self.xml_object.script_settings

    @script_settings.setter
    def script_settings(self, value: list[ScriptReference]) -> None:
        self.xml_object.script_settings = value

    @property
    def urls(self) -> list[CollectionUrl]:
        self.push_to_xml_object()
        return self.xml_object.urls

    @urls.setter
    def urls(self, value: list[CollectionUrl]) -> None:
        self.xml_object.urls = value
        self.pull_from_xml_object()

    @property
    def downloader(self) -> MusicSyncDownloader | None:
        return self.xml_object.downloader

    @downloader.setter
    def downloader(self, value: MusicSyncDownloader | None) -> None:
        self.xml_object.downloader = value

    def get_text(self) -> str:
        return self.xml_object.name

    def set_text(self, value: str):
        self.xml_object.name = value

    def pull_from_xml_object(self):
        self.remove_rows(0, self.row_count())

        for url in self.xml_object.urls:
            self.append_row(CollectionUrlItem(url))

    def push_to_xml_object(self):
        children = []
        for i in range(self.row_count()):
            child = self.child(i)
            child.push_to_xml_object()
            children.append(child.xml_object)

        self.xml_object.urls = children

    def compare(self, progress_callback: Callable[[float, str], None] | None=None, interruption_callback: Callable[[], bool] | None=None) -> pd.DataFrame | Exception:
        assert self.xml_object is not None

        self.push_to_xml_object()
        result = self.xml_object.compare(progress_callback=progress_callback, interruption_callback=interruption_callback)
        self.pull_from_xml_object()

        return result

    def sync(self, info_df: pd.DataFrame, progress_callback: Callable[[float, str], None] | None = None,
             interruption_callback: Callable[[], bool] | None = None) -> None | Exception:
        assert self.xml_object is not None

        self.push_to_xml_object()
        result = self.xml_object.sync(info_df, progress_callback, interruption_callback)
        self.pull_from_xml_object()
        return result

    def get_real_path(self, url: 'CollectionUrl', track=None):
        self.push_to_xml_object()
        return self.xml_object.get_real_path(url, track)


class CollectionUrlItem(XmlObjectModelItem):
    def __init__(self, xml_object: CollectionUrl | None = None, **kwargs):
        super().__init__(xml_object, icon=QIcon.fromTheme('folder-remote'))
        if xml_object is None:
            self.xml_object: CollectionUrl = CollectionUrl(**kwargs)
        else:
            self.xml_object: CollectionUrl = xml_object

        self.pull_from_xml_object()

    @property
    def name(self) -> str:
        return self.xml_object.name

    @name.setter
    def name(self, value: str) -> None:
        self.xml_object.name = value

    @property
    def url(self) -> str:
        return self.xml_object.url

    @url.setter
    def url(self, value: str) -> None:
        self.xml_object.url = value

    @property
    def tracks(self) -> pd.DataFrame:
        return self.xml_object.tracks

    @tracks.setter
    def tracks(self, value: pd.DataFrame) -> None:
        self.xml_object.tracks = value

    @property
    def excluded(self) -> bool:
        return self.xml_object.excluded

    @excluded.setter
    def excluded(self, value: bool) -> None:
        self.xml_object.excluded = value

    @property
    def concat(self) -> bool:
        return self.xml_object.concat

    @concat.setter
    def concat(self, value: bool) -> None:
        self.xml_object.concat = value

    @property
    def is_playlist(self) -> bool | None:
        return self.xml_object.is_playlist

    @is_playlist.setter
    def is_playlist(self, value: bool) -> None:
        self.xml_object.is_playlist = value

    @property
    def save_to_subfolder(self) -> bool:
        return self.xml_object.save_to_subfolder

    @save_to_subfolder.setter
    def save_to_subfolder(self, value: bool) -> None:
        self.xml_object.save_to_subfolder = value

    def get_text(self) -> str:
        return self.xml_object.name or self.xml_object.url

    def set_text(self, value: str):
        resolved = not self.font.italic()
        if resolved:
            self.xml_object.name = value
        else:
            self.xml_object.url = value

    def pull_from_xml_object(self):
        f = self.font
        if self.xml_object.name:
            f.setItalic(False)
        else:
            f.setItalic(True)

        self.font = f

    def push_to_xml_object(self):
        pass