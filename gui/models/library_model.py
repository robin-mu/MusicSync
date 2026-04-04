import os
from typing import cast, Union
from xml.etree.ElementTree import Element

import pandas as pd
from PySide6.QtGui import QIcon

from downloader import MusicSyncDownloader
from musicsync.music_sync_library import Collection, CollectionUrl, Folder, MusicSyncLibrary, Script, PathComponent, \
    TrackSyncStatus, TrackSyncAction, ScriptReference
from .xml_model import XmlObjectModel, XmlObjectModelItem


class LibraryModel(XmlObjectModel):
    def __init__(self, path: str=None):
        super(LibraryModel, self).__init__()

        self.root = self.invisibleRootItem()
        self.saved_library_object: MusicSyncLibrary | None = None
        self.library_object: MusicSyncLibrary | None = None

        if path is not None:
            # self.loaded_library_object = MusicSyncLibrary.read_pickle(path)
            self.saved_library_object = MusicSyncLibrary.read_xml(path)  # only used to determine if library has been changed before saving
            self.library_object = MusicSyncLibrary.read_xml(path)  # has to be a copy, not the same object as saved_library_object

            assert self.library_object is not None  # make ide happy

            for child in self.library_object.children:
                if isinstance(child, Folder):
                    self.root.appendRow(FolderItem.from_xml_object(child))
                elif isinstance(child, Collection):
                    self.root.appendRow(CollectionItem.from_xml_object(child))

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

    @staticmethod
    def item_from_xml(el: Element) -> XmlObjectModelItem:
        if el.tag == 'Folder':
            return FolderItem.from_xml_object(Folder.from_xml(el))
        elif el.tag == 'Collection':
            return CollectionItem.from_xml_object(Collection.from_xml(el))
        elif el.tag == 'CollectionUrl':
            return CollectionUrlItem.from_xml_object(CollectionUrl.from_xml(el))

        raise ValueError(f'Unknown tag {el.tag}')

    @staticmethod
    def validate_drop(parent_item: XmlObjectModelItem | None, item: XmlObjectModelItem) -> bool:
        if (parent_item is None or isinstance(parent_item, FolderItem)) and isinstance(item, CollectionUrlItem):
            return False

        if isinstance(parent_item, CollectionItem) and (isinstance(item, (CollectionItem, FolderItem))):
            return False

        if isinstance(parent_item, CollectionUrlItem):
            return False

        return True

    def to_library_object(self) -> MusicSyncLibrary:
        children = []
        for i in range(self.root.rowCount()):
            row = cast(XmlObjectModelItem, self.root.child(i))
            children.append(row.to_xml_object())
        return MusicSyncLibrary(scripts=self.scripts,
                                metadata_table=self.metadata_table,
                                children=children)

    def to_xml(self, filename: str | None=None):
        if filename is None:
            filename = self.path

        if filename.endswith('.pkl'):
            filename = filename[:-4] + '.xml'

        lib_object = self.to_library_object()
        self.saved_library_object = lib_object
        lib_object.write_xml(filename)

    def to_pickle(self, filename: str | None=None):
        if filename is None:
            filename = self.path
        lib_object = self.to_library_object()
        self.saved_library_object = lib_object
        lib_object.write_pickle(filename)

    def has_changed(self):
        if self.root.rowCount() == 0:
            return False

        if self.saved_library_object is None:
            return True

        return self.to_library_object() != self.saved_library_object

    @staticmethod
    def add_folder(parent: FolderItem):
        new_folder = FolderItem()
        parent.appendRow(new_folder)
        return new_folder

    @staticmethod
    def add_collection(parent: FolderItem):
        new_collection = CollectionItem()
        parent.appendRow(new_collection)
        return new_collection

    @staticmethod
    def add_url(parent: CollectionItem, url: str='', name: str= ''):
        new_url = CollectionUrlItem(url=url, name=name, concat=parent.auto_concat_urls, resolved=False)
        parent.appendRow(new_url)
        return new_url


class FolderItem(XmlObjectModelItem):
    def __init__(self, xml_object: Folder | None = None, **kwargs):
        super().__init__()
        if xml_object is None:
            self.xml_object = Folder(**kwargs)
        else:
            self.xml_object = xml_object

        self.pull_from_xml_object()

        self.setIcon(QIcon.fromTheme('folder'))

    @property
    def name(self) -> str:
        self.push_to_xml_object(only_name=True)
        return self.xml_object.name

    @name.setter
    def name(self, value: str) -> None:
        self.xml_object.name = value
        self.pull_from_xml_object(only_name=True)

    @property
    def children(self) -> list[Union['Folder', 'Collection']]:
        self.push_to_xml_object()
        return self.xml_object.children

    @children.setter
    def children(self, value: list[Union['Folder', 'Collection']]):
        self.xml_object.children = value
        self.pull_from_xml_object()


    def pull_from_xml_object(self, only_name: bool = False):
        self.setText(self.xml_object.name)

        if only_name:
            return

        self.removeRows(0, self.rowCount())

        for child in self.xml_object.children:
            if isinstance(child, Folder):
                self.appendRow(FolderItem(child))
            elif isinstance(child, Collection):
                self.appendRow(CollectionItem(child))


    def push_to_xml_object(self, only_name: bool = False):
        self.xml_object.name = self.text()

        if only_name:
            return

        children = []
        for i in range(self.rowCount()):
            child = self.child(i)
            child.push_to_xml_object()
            children.append(child.xml_object)

        self.xml_object.children = children


class CollectionItem(XmlObjectModelItem):
    def __init__(self, xml_object: Collection | None = None, **kwargs):
        super().__init__()
        if xml_object is None:
            self.xml_object = Collection(**kwargs)
        else:
            self.xml_object = xml_object

        self.pull_from_xml_object()

        self.setIcon(QIcon.fromTheme('text-x-generic'))

        self.comparing: bool = False
        self.syncing: bool = False
        self.sync_progress: float = 0
        self.sync_text: str = ''
        self.compare_result: pd.DataFrame | None = None

    @property
    def name(self) -> str:
        self.push_to_xml_object(only_name=True)
        return self.xml_object.name

    @name.setter
    def name(self, value: str) -> None:
        self.xml_object.name = value
        self.pull_from_xml_object(only_name=True)

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

    def pull_from_xml_object(self, only_name: bool = False):
        self.setText(self.xml_object.name)

        if only_name:
            return

        self.removeRows(0, self.rowCount())

        for url in self.xml_object.urls:
            self.appendRow(CollectionUrlItem(url))

    def push_to_xml_object(self, only_name: bool = False):
        self.xml_object.name = self.text()

        if only_name:
            return

        children = []
        for i in range(self.rowCount()):
            child = self.child(i)
            child.push_to_xml_object()
            children.append(child.xml_object)

        self.xml_object.urls = children

    def get_real_path(self, url: 'CollectionUrl', track=None):
        self.push_to_xml_object()
        return self.xml_object.get_real_path(url, track)

    def child(self, row, *args) -> 'CollectionUrlItem':
        return cast(CollectionUrlItem, super().child(row, *args))


class CollectionUrlItem(XmlObjectModelItem):
    def __init__(self, xml_object: CollectionUrl | None = None, **kwargs):
        super().__init__()
        if xml_object is None:
            self.xml_object: CollectionUrl = CollectionUrl(**kwargs)
        else:
            self.xml_object: CollectionUrl = xml_object

        self.pull_from_xml_object()

        self.setIcon(QIcon.fromTheme('folder-remote'))

    @property
    def name(self) -> str:
        self.push_to_xml_object()
        return self.xml_object.name

    @name.setter
    def name(self, value: str) -> None:
        self.xml_object.name = value
        self.pull_from_xml_object()

    @property
    def url(self) -> str:
        self.push_to_xml_object()
        return self.xml_object.url

    @url.setter
    def url(self, value: str) -> None:
        self.xml_object.url = value
        self.pull_from_xml_object()

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

    def pull_from_xml_object(self):
        f = self.font()
        if self.xml_object.name:
            f.setItalic(False)
            self.setText(self.xml_object.name)
        else:
            f.setItalic(True)
            self.setText(self.xml_object.url)

        self.setFont(f)

    def push_to_xml_object(self):
        resolved = not self.font().italic()

        name = self.text() if resolved else ''
        url = self.xml_object.url if resolved else self.text()

        self.xml_object.name = name
        self.xml_object.url = url

    # for correct types
    def parent(self, /) -> 'CollectionItem':
        return cast(CollectionItem, super().parent())