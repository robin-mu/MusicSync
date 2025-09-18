import ast
from dataclasses import dataclass, field
import xml.etree.ElementTree as et
from enum import Enum
from typing import Union
from xml.etree.ElementTree import Element

import pandas as pd
from yt_dlp import YoutubeDL

from src.bookmark_library import BookmarkLibrary, BookmarkFolder


@dataclass
class MusicSyncLibrary:
    metadata_table_path: str = ''
    children: list[Union['Folder', 'Collection']] = field(default_factory=list)

    @staticmethod
    def read_xml(xml_path: str) -> 'MusicSyncLibrary':
        tree = et.parse(xml_path)
        root = tree.getroot()
        children = []
        for child in root:
            if child.tag == 'Folder':
                children.append(Folder.from_xml(child))
            elif child.tag == 'Collection':
                children.append(Collection.from_xml(child))

        return MusicSyncLibrary(children=children, **root.attrib)

    def write_xml(self, xml_path: str):
        attrs = vars(self).copy()
        attrs.pop('children')

        root = et.Element('MusicSyncLibrary', **attrs)
        for child in self.children:
            root.append(child.to_xml())

        et.ElementTree(root).write(xml_path)


@dataclass
class Folder:
    name: str
    children: list[Union['Folder', 'Collection']] = field(default_factory=list)

    @staticmethod
    def from_xml(el: Element) -> 'Folder':
        children = []
        for child in el:
            if child.tag == 'Folder':
                children.append(Folder.from_xml(child))
            elif child.tag == 'Collection':
                children.append(Collection.from_xml(child))

        return Folder(children=children, **el.attrib)

    def to_xml(self) -> Element:
        attrs = vars(self).copy()
        attrs.pop('children')

        el = et.Element('Folder', **attrs)
        for child in self.children:
            el.append(child.to_xml())
        return el

@dataclass
class Collection:
    name: str
    folder_path: str = ''
    filename_format: str = ''
    file_extension: str = ''
    file_tags: str = ''
    save_playlists_to_subfolders: bool = False
    urls: list['CollectionUrl'] = field(default_factory=list)
    sync_bookmark_file: str = ''
    sync_bookmark_folder: list[tuple[str, str]] = field(default_factory=list)
    sync_bookmark_title_as_url_name: bool = False

    def __post_init__(self):
        if isinstance(self.save_playlists_to_subfolders, str):
            self.save_playlists_to_subfolders = self.save_playlists_to_subfolders == 'True'
        if isinstance(self.sync_bookmark_title_as_url_name, str):
            self.sync_bookmark_title_as_url_name = self.sync_bookmark_title_as_url_name == 'True'

        if isinstance(self.sync_bookmark_folder, str):
            self.sync_bookmark_folder = ast.literal_eval(self.sync_bookmark_folder)

    @staticmethod
    def from_xml(el: Element) -> 'Collection':
        urls = []
        for child in el:
            if child.tag == 'CollectionUrl':
                urls.append(CollectionUrl.from_xml(child))

        return Collection(urls=urls, **el.attrib)

    def to_xml(self) -> Element:
        attrs = vars(self).copy()
        attrs.pop('urls')
        attrs['save_playlists_to_subfolders'] = str(self.save_playlists_to_subfolders)
        attrs['sync_bookmark_folder'] = str(self.sync_bookmark_folder)
        attrs['sync_bookmark_title_as_url_name'] = str(self.sync_bookmark_title_as_url_name)

        el = et.Element('Collection', **attrs)
        for url in self.urls:
            el.append(url.to_xml())
        return el

    def update_sync_status(self):
        # updating collection urls if sync with bookmarks is enabled
        if self.sync_bookmark_file:
            bookmarks = BookmarkLibrary.create_from_path(self.sync_bookmark_file)
            folder = bookmarks.go_to_path([e[0] for e in self.sync_bookmark_folder])
            flattened = BookmarkFolder.flatten(folder)
            for child in flattened.values():
                if child.url not in self.urls:
                    self.urls.append(CollectionUrl(url=child.url, name=child.bookmark_title if self.sync_bookmark_title_as_url_name else ''))

        ydl_opts = {
            'default_search': 'ytsearch',
            'compat_opts': ['no-youtube-unavailable-videos']
        }

        ydl = YoutubeDL(ydl_opts)
        sync_status = pd.DataFrame()

        # download track info of all collection urls
        for url in self.urls:
            info = ydl.extract_info(url.url, process=False)
            if info['_type'] == 'playlist':
                playlist_tracks = set([e['url'] for e in info['entries']])
                new_tracks = playlist_tracks - url.tracks
                deleted_tracks = url.tracks - playlist_tracks



@dataclass
class CollectionUrl:
    url: str
    name: str = ''
    tracks: set[str] = field(default_factory=set)

    @staticmethod
    def from_xml(el: Element) -> 'CollectionUrl':
        tracks = []
        for child in el:
            if child.tag == 'Track':
                tracks.append(child.text)
        return CollectionUrl(**el.attrib)

    def to_xml(self) -> Element:
        attrs = vars(self).copy()
        attrs.pop('tracks')

        el = et.Element('CollectionUrl', **attrs)
        for track in self.tracks:
            track_el = et.Element('Track')
            track_el.text = track
            el.append(track_el)
        return el

class TrackSyncStatus(Enum):
    AddedToPlaylist = 1
    NotDownloaded = 2
    RemovedFromPlaylist = 3
    Downloaded = 4


if __name__ == '__main__':
    print(MusicSyncLibrary().read_xml('../library.xml').children[0].children[0].update_sync_status())