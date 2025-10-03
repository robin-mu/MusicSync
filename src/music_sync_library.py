import xml.etree.ElementTree as et
from copy import deepcopy
from dataclasses import dataclass, field
from enum import auto, StrEnum
from pprint import pprint
from typing import Union, ClassVar, Any
from xml.etree.ElementTree import Element

import pandas as pd
import yt_dlp
from yt_dlp import YoutubeDL
from yt_dlp.postprocessor import FFmpegMetadataPP

from src.bookmark_library import BookmarkLibrary
from src.xml_object import XmlObject


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
class Folder(XmlObject):
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


class TrackSyncStatus(StrEnum):
    ADDED_TO_SOURCE = auto()
    """
    Track is present in source, but was not present in previous sync
    """
    NOT_DOWNLOADED = auto()
    """
    Track is present in source, was also present in previous sync, but corresponding file does not exist
    """
    REMOVED_FROM_SOURCE = auto()
    """
    Track is not present in source, but was present in previous sync
    """
    LOCAL_FILE = auto()
    """
    File is not in the permanently downloaded files, and does not correspond to a source track
    """
    PERMANENTLY_DOWNLOADED = auto()
    """
    File is present in the permanently downloaded files
    """
    DOWNLOADED = auto()
    """
    Track is present in source and the corresponding file exists
    """


class TrackSyncAction(StrEnum):
    DOWNLOAD = auto(), 'Download', 'Download the file'
    """
    Download the file
    """
    DELETE = auto(), 'Delete the file', 'Delete the file'
    """
    Delete the file
    """
    DO_NOTHING = auto(), 'Do nothing', 'Don\'t delete or download any file and don\'t change the configuration'
    """
    Don't delete or download any file and don't change the configuration. Effectively does nothing
    """
    KEEP_PERMANENTLY = auto(), 'Add file to permanently downloaded files', 'Don\'t delete the file and add it to the list of permanently downloaded files saved in the collection settings'
    """
    Don't delete the file and add it to the list of permanently downloaded files
    """
    REMOVE_FROM_PERMANENTLY_DOWNLOADED = auto(), 'Remove file from permanently downloaded files', 'Remove the file from the list of permanently downloaded files (but don\'t delete the file)'
    """
    Remove the file from the list of permanently downloaded files (but don't delete the file)
    """
    DECIDE_INDIVIDUALLY = auto(), 'Decide individually', 'You have to pick an action in each case. Syncing can only start when none of the selected actions are "Decide individually"'
    """
    Let the user decide in each case. Syncing can only start when none of the selected actions are ``DECIDE_INDIVIDUALLY``
    """

    def __new__(cls, value, gui_string, gui_status_tip):
        obj = str.__new__(cls, value)
        obj._value_ = value
        obj._sort_key = len(cls.__members__)
        obj._gui_string = gui_string
        obj._gui_status_tip = gui_status_tip
        return obj

    @property
    def sort_key(self) -> int:
        return self._sort_key

    @property
    def gui_string(self) -> str:
        return self._gui_string

    @property
    def gui_status_tip(self) -> str:
        return self._gui_status_tip

@dataclass
class MetadataField(XmlObject):
    name: str
    suggestions: list['MetadataSuggestion']
    enabled: bool = True
    show_format_options: bool = False
    default_format_as_title: bool = False
    default_remove_brackets: bool = False

    def __post_init__(self):
        if isinstance(self.show_format_options, str):
            self.show_format_options = self.show_format_options == 'True'
        if isinstance(self.default_format_as_title, str):
            self.default_format_as_title = self.default_format_as_title == 'True'
        if isinstance(self.default_remove_brackets, str):
            self.default_remove_brackets = self.default_remove_brackets == 'True'

    @staticmethod
    def from_xml(el: Element) -> 'XmlObject':
        suggestions = []
        for child in el:
            suggestions.append(MetadataSuggestion.from_xml(child))

        return MetadataField(**(el.attrib | {'suggestions': suggestions}))


    def to_xml(self) -> Element:
        attrs = vars(self).copy()
        attrs.pop('suggestions')
        attrs['show_format_options'] = str(self.show_format_options)
        attrs['default_format_as_title'] = str(self.default_format_as_title)
        attrs['default_remove_brackets'] = str(self.default_remove_brackets)

        el = et.Element('MetadataColumn', **attrs)
        for suggestion in self.suggestions:
            el.append(suggestion.to_xml())
        return el


@dataclass
class MetadataSuggestion(XmlObject):
    pattern_from: str
    pattern_to: str = ''
    split_separators: str = ''
    split_slice: str = ''

    @staticmethod
    def from_xml(el: Element) -> 'XmlObject':
        return MetadataSuggestion(**el.attrib)

    def to_xml(self) -> et.Element:
        return et.Element('MetadataSuggestion', **vars(self))


@dataclass
class Collection(XmlObject):
    DEFAULT_SYNC_ACTIONS: ClassVar[dict[TrackSyncStatus, TrackSyncAction]] = {
        TrackSyncStatus.ADDED_TO_SOURCE: TrackSyncAction.DOWNLOAD,
        TrackSyncStatus.NOT_DOWNLOADED: TrackSyncAction.DOWNLOAD,
        TrackSyncStatus.REMOVED_FROM_SOURCE: TrackSyncAction.DECIDE_INDIVIDUALLY,
        TrackSyncStatus.LOCAL_FILE: TrackSyncAction.DO_NOTHING,
        TrackSyncStatus.PERMANENTLY_DOWNLOADED: TrackSyncAction.DO_NOTHING,
        TrackSyncStatus.DOWNLOADED: TrackSyncAction.DO_NOTHING,
    }

    # field for suggestion from yt_dlp's metadata with name "field"
    # 0_field for suggestion from this table column with name "field"
    # 1_field for suggestion from external table column with name "field"
    DEFAULT_METADATA_SUGGESTIONS: ClassVar[list['MetadataField']] = [
            MetadataField('title', suggestions=[
                MetadataSuggestion('0_title'),
                MetadataSuggestion('track'),
                MetadataSuggestion('title', split_separators=' - , – , — ,-,|,:,~,‐,_,∙', split_slice='::-1'),
                MetadataSuggestion('title', '["“](?P<>.+)["“]'),
                MetadataSuggestion('title')
            ], show_format_options=True, default_format_as_title=True, default_remove_brackets=True),
            MetadataField('artist', suggestions=[
                MetadataSuggestion('0_artist'),
                MetadataSuggestion('artist', split_separators=r'\,'),
                MetadataSuggestion('title', split_separators=' - , – , — ,-,|,:,~,‐,_,∙',),
                MetadataSuggestion('title', ' by (?P<>.+)'),
                MetadataSuggestion('channel'),
                MetadataSuggestion('title')
            ], show_format_options=True, default_format_as_title=True, default_remove_brackets=True),
            MetadataField('album', suggestions=[
                MetadataSuggestion('0_album'),
                MetadataSuggestion('album'),
                MetadataSuggestion('playlist'),
            ], show_format_options=True, default_format_as_title=True, default_remove_brackets=True),
            MetadataField('track', suggestions=[
                MetadataSuggestion('0_track'),
                MetadataSuggestion('track'),
                MetadataSuggestion('playlist_index'),
            ])
        ]

    name: str
    folder_path: str = ''
    filename_format: str = ''
    file_extension: str = ''
    file_tags: str = ''
    save_playlists_to_subfolders: bool = False
    urls: list['CollectionUrl'] = field(default_factory=list)
    sync_bookmark_file: str = ''
    sync_bookmark_path: list[tuple[str, str]] = field(default_factory=list)
    sync_bookmark_title_as_url_name: bool = False
    exclude_after_download: bool = False
    sync_actions: dict[TrackSyncStatus, TrackSyncAction] = field(
        default_factory=lambda: Collection.DEFAULT_SYNC_ACTIONS.copy())
    metadata_suggestions: list[
        'MetadataField'] = field(default_factory=lambda: deepcopy(Collection.DEFAULT_METADATA_SUGGESTIONS))

    def __post_init__(self):
        if isinstance(self.save_playlists_to_subfolders, str):
            self.save_playlists_to_subfolders = self.save_playlists_to_subfolders == 'True'
        if isinstance(self.sync_bookmark_title_as_url_name, str):
            self.sync_bookmark_title_as_url_name = self.sync_bookmark_title_as_url_name == 'True'
        if isinstance(self.exclude_after_download, str):
            self.exclude_after_download = self.exclude_after_download == 'True'

    @staticmethod
    def from_xml(el: Element) -> 'Collection':
        kwargs: dict[str, Any] = {'urls': []}
        for child in el:
            if child.tag == 'BookmarkSync':
                kwargs['sync_bookmark_file'] = child.attrib['file']
                kwargs['sync_bookmark_title_as_url_name'] = child.attrib['title_as_url_name']
                kwargs['sync_bookmark_path'] = []
                for path_component in child:
                    kwargs['sync_bookmark_path'].append((path_component.attrib['id'], path_component.attrib['name']))
            elif child.tag == 'SyncActions':
                kwargs['sync_actions'] = {TrackSyncStatus(k): TrackSyncAction(v) for k, v in child.attrib.items()}
            elif child.tag == 'CollectionUrl':
                kwargs['urls'].append(CollectionUrl.from_xml(child))
            elif child.tag == 'MetadataSuggestions':
                kwargs['metadata_suggestions'] = []
                for column in child:
                    kwargs['metadata_suggestions'].append(MetadataField.from_xml(column))

        return Collection(**(kwargs | el.attrib))

    def to_xml(self) -> Element:
        attrs = vars(self).copy()
        attrs.pop('urls')
        attrs.pop('sync_bookmark_file')
        attrs.pop('sync_bookmark_path')
        attrs.pop('sync_bookmark_title_as_url_name')
        attrs.pop('sync_actions')
        attrs.pop('metadata_suggestions')
        attrs['save_playlists_to_subfolders'] = str(self.save_playlists_to_subfolders)
        attrs['exclude_after_download'] = str(self.exclude_after_download)

        el = et.Element('Collection', **attrs)
        if self.sync_bookmark_file:
            bookmark_sync = et.Element('BookmarkSync', file=self.sync_bookmark_file,
                                       title_as_url_name=str(self.sync_bookmark_title_as_url_name))
            for idx, folder in self.sync_bookmark_path:
                bookmark_sync.append(et.Element('PathComponent', id=idx, name=folder))
            el.append(bookmark_sync)

        if self.sync_actions != Collection.DEFAULT_SYNC_ACTIONS:
            el.append(et.Element('SyncActions', **self.sync_actions))

        if self.metadata_suggestions != Collection.DEFAULT_METADATA_SUGGESTIONS:
            suggestions = et.Element('MetadataSuggestions')
            for suggestion in self.metadata_suggestions:
                suggestions.append(suggestion.to_xml())
            el.append(suggestions)

        for url in self.urls:
            el.append(url.to_xml())
        return el

    def update_sync_status(self):
        # updating collection urls if sync with bookmarks is enabled
        if self.sync_bookmark_file:
            bookmarks = BookmarkLibrary.create_from_path(self.sync_bookmark_file)
            folder = bookmarks.go_to_path([e[0] for e in self.sync_bookmark_path]).get_all_bookmarks()
            for child in folder.values():
                if child.url not in self.urls:
                    self.urls.append(CollectionUrl(url=child.url,
                                                   name=child.bookmark_title if self.sync_bookmark_title_as_url_name else ''))

        ydl_opts = {'final_ext': 'mp3',
                    'format': 'ba[acodec^=mp3]/ba/b',
                    'outtmpl': {'pl_thumbnail': ''},
                    'writethumbnail': True,
                    'postprocessors': [{'actions': [(yt_dlp.postprocessor.metadataparser.MetadataParserPP.interpretter,
                                                     '%(playlist_index)s',
                                                     '%(meta_track)s')],
                                        'key': 'MetadataParser',
                                        'when': 'pre_process'},
                                       {'key': 'FFmpegExtractAudio',
                                        'nopostoverwrites': False,
                                        'preferredcodec': 'mp3',
                                        'preferredquality': '5'},
                                       {'add_chapters': True,
                                        'add_infojson': 'if_exists',
                                        'add_metadata': True,
                                        'key': 'FFmpegMetadata'},
                                       {'already_have_thumbnail': False, 'key': 'EmbedThumbnail'}],
                    'compat_opts': ['no-youtube-unavailable-videos']
                    }

        ydl = YoutubeDL(ydl_opts)
        sync_status = pd.DataFrame()
        ydl.add_post_processor(YTMusicAlbumCover(), 'pre_process')

        # download track info of all collection urls
        for url in self.urls:
            info = ydl.extract_info(url.url, process=False)
            if info['_type'] == 'playlist':
                entries = list(info['entries'])
                playlist_tracks = set([e['url'] for e in entries])
                info['entries'] = entries
            pprint(info)

            info = ydl.process_ie_result(info, download=True)
            pprint(info)


class YTMusicAlbumCover(yt_dlp.postprocessor.PostProcessor):
    # set 1:1 album cover to be embedded (only for yt-music)
    def run(self, info):
        for t in info['thumbnails']:
            if t['id'] == '2':
                info['thumbnail'] = t['url']
                info['thumbnails'] = [t]
                break
        return [], info


@dataclass
class CollectionUrl(XmlObject):
    url: str
    name: str = ''
    excluded: bool = False
    tracks: list[str] = field(default_factory=list)

    def __post_init__(self):
        if isinstance(self.excluded, str):
            self.excluded = self.excluded == 'True'

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
        attrs['excluded'] = str(self.excluded)

        el = et.Element('CollectionUrl', **attrs)
        for track in self.tracks:
            track_el = et.Element('Track')
            track_el.text = track
            el.append(track_el)
        return el


if __name__ == '__main__':
    # print(MusicSyncLibrary().read_xml('../library.xml').children[0].children[0].update_sync_status())


    info = {
        'ext': 'mp3',
        'filepath': 'Mili - TIAN TIAN [Limbus Company] [szyPY8nbBF4].mp3',
        'track': 'Test'
    }
    FFmpegMetadataPP(None).run(info)