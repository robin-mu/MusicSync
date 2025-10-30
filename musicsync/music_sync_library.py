import os
import xml.etree.ElementTree as et
from collections import namedtuple
from dataclasses import dataclass, field
from enum import StrEnum, auto
from pprint import pprint
from typing import Any, ClassVar, Union, Callable
from xml.etree.ElementTree import Element

import pandas as pd
import yt_dlp
from yt_dlp import MetadataParserPP, YoutubeDL

import musicsync.download.downloader as dl
from .xml_object import XmlObject
from .utils import classproperty


@dataclass
class MusicSyncLibrary:
    metadata_table_path: str = ''
    external_metadata_tables: list['ExternalMetadataTable'] = field(default_factory=list)
    children: list[Union['Folder', 'Collection']] = field(default_factory=list)

    @staticmethod
    def read_xml(xml_path: str) -> 'MusicSyncLibrary':
        tree = et.parse(xml_path)
        root = tree.getroot()
        children = []
        external_metadata_tables = []
        for child in root:
            if child.tag == 'Folder':
                children.append(Folder.from_xml(child))
            elif child.tag == 'Collection':
                children.append(Collection.from_xml(child))
            elif child.tag == 'ExternalMetadataTable':
                external_metadata_tables.append(ExternalMetadataTable.from_xml(child))

        return MusicSyncLibrary(children=children, external_metadata_tables=external_metadata_tables, **root.attrib)

    def write_xml(self, xml_path: str):
        attrs = vars(self).copy()
        attrs.pop('children')
        attrs.pop('external_metadata_tables')

        root = et.Element('MusicSyncLibrary', **attrs)
        for table in self.external_metadata_tables:
            root.append(table.to_xml())
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
    ADDED_TO_SOURCE = auto(), 'Track added to URL', 'Track is present online, but was not present in the previous sync.'
    """
    Track is present online, but was not present in the previous sync.
    """
    NOT_DOWNLOADED = auto(), 'Track not downloaded', 'Track is present online, was also present in previous sync, but the corresponding file does not exist.'
    """
    Track is present online, was also present in previous sync, but the corresponding file does not exist.
    """
    REMOVED_FROM_SOURCE = auto(), 'Track removed from URL', 'Track is not present online, but was present in the previous sync.'
    """
    Track is not present online, but was present in the previous sync.
    """
    LOCAL_FILE = auto(), 'File only exists locally', 'The file is not marked as permanently downloaded and does not correspond to a track found online.'
    """
    The file is not marked as permanently downloaded and does not correspond to a track found online.
    """
    PERMANENTLY_DOWNLOADED = auto(), 'File permanently downloaded', 'The file is marked as permanently downloaded (even though its corresponding track might not exist anymore).'
    """
    The file is marked as permanently downloaded (even though its corresponding track might not exist anymore).
    """
    DOWNLOADED = auto(), 'File downloaded', 'Track is present online and the corresponding file exists.'
    """
    Track is present online and the corresponding file exists.
    """

    @classproperty
    def ACTION_OPTIONS(self):
        return {
            TrackSyncStatus.ADDED_TO_SOURCE: [TrackSyncAction.DOWNLOAD, TrackSyncAction.DO_NOTHING,
                                              TrackSyncAction.DECIDE_INDIVIDUALLY],
            TrackSyncStatus.NOT_DOWNLOADED: [TrackSyncAction.DOWNLOAD, TrackSyncAction.DO_NOTHING,
                                             TrackSyncAction.DECIDE_INDIVIDUALLY],
            TrackSyncStatus.REMOVED_FROM_SOURCE: [TrackSyncAction.DELETE, TrackSyncAction.DO_NOTHING,
                                                  TrackSyncAction.KEEP_PERMANENTLY,
                                                  TrackSyncAction.DECIDE_INDIVIDUALLY],
            TrackSyncStatus.LOCAL_FILE: [TrackSyncAction.DELETE, TrackSyncAction.DO_NOTHING,
                                         TrackSyncAction.KEEP_PERMANENTLY, TrackSyncAction.DECIDE_INDIVIDUALLY],
            TrackSyncStatus.PERMANENTLY_DOWNLOADED: [TrackSyncAction.DO_NOTHING,
                                                     TrackSyncAction.REMOVE_FROM_PERMANENTLY_DOWNLOADED,
                                                     TrackSyncAction.DECIDE_INDIVIDUALLY],
            TrackSyncStatus.DOWNLOADED: [TrackSyncAction.DO_NOTHING, TrackSyncAction.DOWNLOAD,
                                         TrackSyncAction.REDOWNLOAD_METADATA, TrackSyncAction.DECIDE_INDIVIDUALLY],
        }

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


class TrackSyncAction(StrEnum):
    DOWNLOAD = auto(), 'Download', 'Download the file.'
    """
    Download the file.
    """
    DELETE = auto(), 'Delete', 'Delete the file and remove the track entry from the URL.'
    """
    Delete the file.
    """
    DO_NOTHING = auto(), 'Do nothing', 'Don\'t delete or download a file and don\'t change the configuration.'
    """
    Don't delete or download a file and don't change the configuration. Effectively does nothing.
    """
    KEEP_PERMANENTLY = auto(), 'Mark as permanently downloaded', 'Don\'t delete the file and mark it as permanently downloaded. This means the file won\'t be marked as "not downloaded" or "removed from collection" in the future.'
    """
    Don't delete the file and mark it as permanently downloaded. This means the file won't be marked as "not downloaded" or "removed from collection" in the future.
    """
    REMOVE_FROM_PERMANENTLY_DOWNLOADED = auto(), 'Mark as not permanently downloaded', 'Mark the file as not permanently downloaded (but don\'t delete the file).'
    """
    Mark the file as not permanently downloaded (but don't delete the file).
    """
    REDOWNLOAD_METADATA = auto(), 'Redownload metadata', 'Download metadata again, but don\'t download the actual file again.'
    """
    Download metadata again, but don't download the actual file again.
    """
    DECIDE_INDIVIDUALLY = auto(), 'Decide individually', 'You have to pick an action in each case. Syncing can only start when none of the selected actions are "Decide individually".'
    """
    You have to pick an action in each case. Syncing can only start when none of the selected actions are "Decide individually".
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
    timed_data: bool = False
    show_format_options: bool = False
    default_format_as_title: bool = False
    default_remove_brackets: bool = False

    def __post_init__(self):
        if isinstance(self.enabled, str):
            self.enabled = self.enabled == 'True'
        if isinstance(self.timed_data, str):
            self.timed_data = self.timed_data == 'True'
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
        attrs['enabled'] = str(self.enabled)
        attrs['timed_data'] = str(self.timed_data)
        attrs['show_format_options'] = str(self.show_format_options)
        attrs['default_format_as_title'] = str(self.default_format_as_title)
        attrs['default_remove_brackets'] = str(self.default_remove_brackets)

        el = et.Element('MetadataField', **attrs)
        for suggestion in self.suggestions:
            el.append(suggestion.to_xml())
        return el


@dataclass
class MetadataSuggestion(XmlObject):
    pattern_from: str
    pattern_to: str = ''
    replace_regex: str = ''
    replace_with: str = ''
    split_separators: str = ''
    split_slice: str = ''
    condition: str = ''

    @staticmethod
    def from_xml(el: Element) -> 'MetadataSuggestion':
        return MetadataSuggestion(**el.attrib)

    def to_xml(self) -> et.Element:
        return et.Element('MetadataSuggestion', **vars(self))


@dataclass
class ExternalMetadataTable(XmlObject):
    id: int = -1
    name: str = ''
    path: str = ''

    def to_xml(self) -> Element:
        return et.Element('ExternalMetadataTable', id=str(self.id), name=self.name, path=self.path)

    @staticmethod
    def from_xml(el: Element) -> 'ExternalMetadataTable':
        return ExternalMetadataTable(id=int(el.attrib['id']), name=el.attrib['name'], path=el.attrib['path'])


@dataclass
class FileTag(XmlObject):
    name: str
    format: str = ''

    @staticmethod
    def from_xml(el: Element) -> 'FileTag':
        return FileTag(**el.attrib)

    def to_xml(self) -> Element:
        return et.Element('FileTag', **vars(self))


@dataclass
class Collection(XmlObject):
    @classproperty
    def DEFAULT_SYNC_ACTIONS(self) -> dict[TrackSyncStatus, TrackSyncAction]:
        return {
            TrackSyncStatus.ADDED_TO_SOURCE: TrackSyncAction.DOWNLOAD,
            TrackSyncStatus.NOT_DOWNLOADED: TrackSyncAction.DOWNLOAD,
            TrackSyncStatus.REMOVED_FROM_SOURCE: TrackSyncAction.DECIDE_INDIVIDUALLY,
            TrackSyncStatus.LOCAL_FILE: TrackSyncAction.DO_NOTHING,
            TrackSyncStatus.PERMANENTLY_DOWNLOADED: TrackSyncAction.DO_NOTHING,
            TrackSyncStatus.DOWNLOADED: TrackSyncAction.DO_NOTHING,
        }

    # field for suggestion from yt_dlp's metadata with name "field"
    # 0:field for suggestion from this table column with name "field"
    # 1:field for suggestion from external table with id 1 and column with name "field"
    @classproperty
    def DEFAULT_METADATA_SUGGESTIONS(self) -> list['MetadataField']:
        return [
            MetadataField('title', suggestions=[
                MetadataSuggestion('track'),
                MetadataSuggestion('title', split_separators=' - , – , — ,-,|,:,~,‐,_,∙', split_slice='::-1'),
                MetadataSuggestion('title', '["“](.+)["“]'),
                MetadataSuggestion('title')
            ], show_format_options=True, default_format_as_title=True, default_remove_brackets=True),
            MetadataField('artist', suggestions=[
                MetadataSuggestion('artist', split_separators=r'\,'),
                MetadataSuggestion('title', split_separators=' - , – , — ,-,|,:,~,‐,_,∙', ),
                MetadataSuggestion('title', ' by (.+)'),
                MetadataSuggestion('channel'),
                MetadataSuggestion('title')
            ], show_format_options=True, default_format_as_title=True, default_remove_brackets=True),
            MetadataField('album', suggestions=[
                MetadataSuggestion('album'),
                MetadataSuggestion('playlist', replace_regex='Album - ', replace_with=''),
            ], show_format_options=True, default_format_as_title=True, default_remove_brackets=True),
            MetadataField('track', suggestions=[
                MetadataSuggestion('track'),
                MetadataSuggestion('playlist_index'),
            ], enabled=False),
            MetadataField('lyrics', suggestions=[
                MetadataSuggestion('EXT_LYRICS:%(0:artist,artist&{} - )s%(0:title,track,title)s')
            ], enabled=False, timed_data=True),
            MetadataField('chapters', suggestions=[
                MetadataSuggestion('%(chapters)s+MULTI_VIDEO:%(title)s'),
            ], enabled=False, timed_data=True),
            MetadataField('thumbnail', suggestions=[
                MetadataSuggestion('%(thumbnails.-1.url)s'),
                MetadataSuggestion('%(thumbnails.2.url)s'),
            ], enabled=False),
            MetadataField('timed_data', suggestions=[
                MetadataSuggestion('%(0:lyrics)s+%(0:chapters)s'),
            ], enabled=False, timed_data=True),
        ]

    @classproperty
    def DEFAULT_FILE_TAGS(self) -> list['FileTag']:
        return [
            FileTag('title', '0:title'),
            FileTag('artist', '0:artist'),
            FileTag('album', '0:album'),
            FileTag('thumbnail', '0:thumbnail'),
        ]

    DEFAULT_FILENAME_FORMAT: ClassVar[str] = '%(title)s [%(id)s]'
    DEFAULT_URL_NAME_FORMAT: ClassVar[str] = '%(title)s'

    PathComponent = namedtuple('PathComponent', ['id', 'name'])

    name: str

    folder_path: str = ''
    filename_format: str = ''
    file_extension: str = ''
    save_playlists_to_subfolders: bool = False
    url_name_format: str = ''
    exclude_after_download: bool = False
    auto_concat_urls: str = ''

    sync_bookmark_file: str = ''
    sync_bookmark_path: list[PathComponent] = field(default_factory=list)
    sync_bookmark_title_as_url_name: bool = False

    sync_actions: dict[TrackSyncStatus, TrackSyncAction] = field(default_factory=lambda: Collection.DEFAULT_SYNC_ACTIONS)

    metadata_suggestions: list['MetadataField'] = field(default_factory=lambda: Collection.DEFAULT_METADATA_SUGGESTIONS)
    file_tags: list['FileTag'] = field(default_factory=lambda: Collection.DEFAULT_FILE_TAGS)

    urls: list['CollectionUrl'] = field(default_factory=list)

    downloader: 'MusicSyncDownloader | None' = None

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
                    kwargs['sync_bookmark_path'].append(Collection.PathComponent(**path_component.attrib))
            elif child.tag == 'SyncActions':
                kwargs['sync_actions'] = {TrackSyncStatus(k): TrackSyncAction(v) for k, v in child.attrib.items()}
            elif child.tag == 'CollectionUrl':
                kwargs['urls'].append(CollectionUrl.from_xml(child))
            elif child.tag == 'MetadataSuggestions':
                kwargs['metadata_suggestions'] = []
                for column in child:
                    if column.tag == 'MetadataField':
                        kwargs['metadata_suggestions'].append(MetadataField.from_xml(column))
            elif child.tag == 'FileTags':
                kwargs['file_tags'] = [FileTag.from_xml(tag) for tag in child]

        return Collection(**(kwargs | el.attrib))

    def to_xml(self) -> Element:
        attrs = vars(self).copy()
        attrs.pop('urls')
        attrs.pop('sync_bookmark_file')
        attrs.pop('sync_bookmark_path')
        attrs.pop('sync_bookmark_title_as_url_name')
        attrs.pop('sync_actions')
        attrs.pop('file_tags')
        attrs.pop('metadata_suggestions')
        attrs.pop('downloader')
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

        if self.file_tags != Collection.DEFAULT_FILE_TAGS:
            file_tags = et.Element('FileTags')
            for file_tag in self.file_tags:
                file_tags.append(file_tag.to_xml())
            el.append(file_tags)

        for url in self.urls:
            el.append(url.to_xml())
        return el

    def update_sync_status(self, progress_callback: Callable | None = None) -> None | Exception:
        if self.downloader is None:
            self.downloader = dl.MusicSyncDownloader(self)

        try:
            self.downloader.update_sync_status(progress_callback=progress_callback)
        except pd.errors.DatabaseError as e:
            return e

    @staticmethod
    def get_real_path(collection: 'Collection | CollectionItem', url: 'CollectionUrl | CollectionUrlItem', track: 'Track | None'=None):
        folder = collection.folder_path
        if collection.save_playlists_to_subfolders and url.is_playlist:
            folder = os.path.join(folder, url.name)
        if track is None:
            return folder
        return os.path.join(folder, track.filename)


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
    concat: bool = False
    is_playlist: bool | None = None
    tracks: dict[str, 'Track'] = field(default_factory=dict)

    def __post_init__(self):
        if isinstance(self.excluded, str):
            self.excluded = self.excluded == 'True'
        if isinstance(self.concat, str):
            self.concat = self.concat == 'True'
        if isinstance(self.is_playlist, str):
            if self.is_playlist == 'None':
                self.is_playlist = None
            else:
                self.is_playlist = self.is_playlist == 'True'

    @staticmethod
    def from_xml(el: Element) -> 'CollectionUrl':
        tracks = {}
        for child in el:
            if child.tag == 'Track':
                track = Track.from_xml(child)
                tracks[track.url] = track
        return CollectionUrl(**el.attrib, tracks=tracks)

    def to_xml(self) -> Element:
        attrs = vars(self).copy()
        attrs.pop('tracks')
        attrs['excluded'] = str(self.excluded)
        attrs['concat'] = str(self.concat)
        attrs['is_playlist'] = str(self.is_playlist)

        el = et.Element('CollectionUrl', **attrs)
        for track in self.tracks.values():
            el.append(track.to_xml())
        return el


@dataclass
class Track(XmlObject):
    url: str
    status: TrackSyncStatus
    title: str
    filename: str = ''
    playlist_index: str = ''
    permanently_downloaded: bool = False

    def __post_init__(self):
        if isinstance(self.permanently_downloaded, str):
            self.permanently_downloaded = self.permanently_downloaded == 'True'

    @staticmethod
    def from_xml(el: Element) -> 'Track':
        return Track(url=el.attrib['url'], status=TrackSyncStatus.__members__[el.attrib['status']],
                     filename=el.attrib['path'], title=el.attrib['title'], playlist_index=el.attrib['playlist_index'],
                     permanently_downloaded=el.attrib['permanently_downloaded'])

    def to_xml(self) -> Element:
        return et.Element('Track', url=self.url, status=self.status.name, path=self.filename,
                          permanently_downloaded=str(self.permanently_downloaded),
                          title=self.title, playlist_index=self.playlist_index)


if __name__ == '__main__':
    # print(MusicSyncLibrary().read_xml('../library.xml').children[0].children[0].update_sync_status())

    info = {
        'ext': 'mp3',
        'filepath': 'Mili - TIAN TIAN [Limbus Company] [szyPY8nbBF4].mp3',
        'track': 'Test',
        'title': 'Mili - TIAN TIAN',
        'test': 1.2345
    }
    # FFmpegMetadataPP(None).run(info)

    info = MetadataParserPP(YoutubeDL(), [(MetadataParserPP.Actions.INTERPRET, '%(title.::-1)s (%(test).2f)',
                                           '%(artist)s - %(title)s'),
                                          (MetadataParserPP.Actions.REPLACE, 'title', r'\((.+)\)', r'-\1-')]).run(info)

    ydl_opts = {'final_ext': 'mp3',
                'format': 'ba[acodec^=mp3]/ba/b',
                'outtmpl': {'pl_thumbnail': ''},
                'writethumbnail': True,
                'postprocessors': [{'actions': [(yt_dlp.postprocessor.metadataparser.MetadataParserPP.interpretter,
                                                 '%(playlist_index)s',
                                                 '%(meta_track)s'),
                                                (yt_dlp.postprocessor.metadataparser.MetadataParserPP.interpretter,
                                                 '%(thumbnails.2.url)s',
                                                 '%(thumbnail_test)s')
                                                ],
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
    info = ydl.extract_info('https://www.youtube.com/watch?v=53bZSTSLUqI', download=False)
    pprint(info)
