import os
from copy import deepcopy
from typing import cast
from xml.etree.ElementTree import Element

import pandas as pd
from PySide6.QtGui import QIcon

from musicsync.music_sync_library import Collection, CollectionUrl, Folder, MusicSyncLibrary, Track, Script
from .xml_model import XmlObjectModel, XmlObjectModelItem


class LibraryModel(XmlObjectModel):
    def __init__(self, path: str=None):
        super(LibraryModel, self).__init__()

        self.path: str = path
        self.root = self.invisibleRootItem()
        self.loaded_library_object: MusicSyncLibrary | None = None
        self.scripts: set['Script'] = set()
        self.metadata_table: pd.DataFrame = pd.DataFrame()

        if path is not None:
            # self.loaded_library_object = MusicSyncLibrary.read_pickle(path)
            self.loaded_library_object = MusicSyncLibrary.read_xml(path)
            self.scripts = self.loaded_library_object.scripts
            self.metadata_table = self.loaded_library_object.metadata_table

            for child in self.loaded_library_object.children:
                if isinstance(child, Folder):
                    self.root.appendRow(FolderItem.from_xml_object(child))
                elif isinstance(child, Collection):
                    self.root.appendRow(CollectionItem.from_xml_object(child))

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
        self.loaded_library_object = lib_object
        lib_object.write_xml(filename)

    def to_pickle(self, filename: str | None=None):
        if filename is None:
            filename = self.path
        lib_object = self.to_library_object()
        self.loaded_library_object = lib_object
        lib_object.write_pickle(filename)

    def has_changed(self):
        if self.root.rowCount() == 0:
            return False

        if self.loaded_library_object is None:
            return True

        return self.to_library_object() != self.loaded_library_object

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
    def add_url(parent: CollectionItem, url: str='', name: str= '', tracks: dict[str, Track] | None=None):
        if tracks is None:
            tracks = {}

        new_url = CollectionUrlItem(url=url, name=name, tracks=tracks,
                                    concat=parent.auto_concat_urls, resolved=False)
        parent.appendRow(new_url)
        return new_url


class FolderItem(XmlObjectModelItem):
    def __init__(self, **kwargs):
        super().__init__()
        self.setText(kwargs.get('name', ''))
        self.setIcon(QIcon.fromTheme('folder'))

    @staticmethod
    def from_xml_object(folder: Folder) -> 'FolderItem':
        folder_item = FolderItem(**vars(folder))
        for child in folder.children:
            if isinstance(child, Folder):
                folder_item.appendRow(FolderItem.from_xml_object(child))
            elif isinstance(child, Collection):
                folder_item.appendRow(CollectionItem.from_xml_object(child))

        return folder_item

    def to_xml_object(self) -> Folder:
        children = []
        for i in range(self.rowCount()):
            child = self.child(i)
            children.append(child.to_xml_object())

        return Folder(name=self.text(), children=children)


class CollectionItem(XmlObjectModelItem):
    def __init__(self, **kwargs):
        super().__init__()

        self.setText(kwargs.get('name', ''))
        self.setIcon(QIcon.fromTheme('text-x-generic'))

        self.folder_path = kwargs.get('folder_path', '')
        self.filename_format = kwargs.get('filename_format', '')
        self.file_extension = kwargs.get('file_extension', '')
        self.save_playlists_to_subfolders = kwargs.get('save_playlists_to_subfolders', False)
        self.sync_bookmark_file = kwargs.get('sync_bookmark_file', '')
        self.sync_bookmark_path = kwargs.get('sync_bookmark_path', '')
        self.sync_bookmark_title_as_url_name = kwargs.get('sync_bookmark_title_as_url_name', False)
        self.sync_delete_files = kwargs.get('sync_delete_files', False)
        self.exclude_after_download = kwargs.get('exclude_after_download', False)
        self.sync_actions = kwargs.get('sync_actions', Collection.DEFAULT_SYNC_ACTIONS.copy())
        self.script_settings = kwargs.get('script_settings', [])
        self.url_name_format = kwargs.get('url_name_format', '')
        self.auto_concat_urls = kwargs.get('auto_concat_urls', False)
        self.excluded_yt_dlp_fields = kwargs.get('excluded_yt_dlp_fields', Collection.DEFAULT_EXCLUDED_YT_DLP_FIELDS)
        self.yt_dlp_options = kwargs.get('yt_dlp_options', '')

        self.comparing: bool = False
        self.syncing: bool = False
        self.sync_progress: float = 0
        self.sync_text: str = ''

    @staticmethod
    def from_xml_object(collection: Collection) -> 'CollectionItem':
        collection_item = CollectionItem(**vars(collection))
        for url in collection.urls:
            collection_item.appendRow(CollectionUrlItem.from_xml_object(url))

        return collection_item

    def to_xml_object(self) -> Collection:
        args = vars(self).copy()
        args.pop('comparing')
        args.pop('syncing')
        args.pop('sync_progress')
        args.pop('sync_text')

        children = []
        for i in range(self.rowCount()):
            child = self.child(i)
            children.append(child.to_xml_object())

        return Collection(name=self.text(), _urls=children, **args)


    def get_real_path(self, url: 'CollectionUrlItem', track: 'Track | None'=None):
        folder = self.folder_path
        if self.save_playlists_to_subfolders and url.is_playlist:
            folder = os.path.join(folder, url.text())
        if track is None:
            return folder
        return os.path.join(folder, track.filename)

    def child(self, row, *args) -> 'CollectionUrlItem':
        return cast(CollectionUrlItem, super().child(row, *args))


class CollectionUrlItem(XmlObjectModelItem):
    def __init__(self, **kwargs):
        super().__init__()
        self.name = kwargs.get('name', '')
        self.url: str = kwargs.get('url', '')
        self.tracks: dict[str, Track] = kwargs.get('tracks', {})
        self.excluded: bool = kwargs.get('excluded', False)
        self.concat: bool = kwargs.get('concat', False)
        self.is_playlist: bool | None = kwargs.get('is_playlist', None)
        self.save_to_subfolder: bool = kwargs.get('save_to_subfolder', False)

        if self.name:
            self.setText(self.name)
        else:
            f = self.font()
            f.setItalic(True)
            self.setFont(f)

            self.setText(self.url)

        self.setIcon(QIcon.fromTheme('folder-remote'))

    @staticmethod
    def from_xml_object(collection_url: CollectionUrl) -> 'CollectionUrlItem':
        return CollectionUrlItem(**(vars(collection_url) | {'tracks': deepcopy(collection_url.tracks)}))

    def to_xml_object(self):
        resolved = not self.font().italic()

        name = self.text() if resolved else ''
        url = self.url if resolved else self.text()

        attr = vars(self).copy()
        attr.pop('name')
        attr.pop('url')

        return CollectionUrl(name=name, url=url, **attr)

    def update(self, collection_url: CollectionUrl):
        self.name = collection_url.name
        self.url = collection_url.url
        self.tracks = collection_url.tracks
        self.excluded = collection_url.excluded
        self.concat = collection_url.concat
        self.is_playlist = collection_url.is_playlist

        f = self.font()
        if self.name:
            f.setItalic(False)
            self.setText(self.name)
        else:
            f.setItalic(True)
            self.setText(self.url)

        self.setFont(f)

    # for correct types
    def parent(self, /) -> 'CollectionItem':
        return cast(CollectionItem, super().parent())