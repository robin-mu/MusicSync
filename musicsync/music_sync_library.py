import os
import pickle
import xml.etree.ElementTree as et
from collections import namedtuple
from dataclasses import dataclass, field
from enum import auto
from typing import Any, ClassVar, Union, Callable
from xml.etree.ElementTree import Element

import pandas as pd
from yt_dlp.postprocessor.common import PostProcessor

import musicsync.downloader as dl
from musicsync.bookmark_library import Bookmark
from musicsync.scripting.script_types import Script
from .utils import classproperty, GuiStrEnum
from .xml_object import XmlObject


class TrackSyncStatus(GuiStrEnum):
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


class TrackSyncAction(GuiStrEnum):
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

class MetadataStatus(GuiStrEnum):
    NEW = auto(), 'New', 'This Track was just downloaded and no custom metadata has been saved yet.'
    REDOWNLOADED = auto(), 'Metadata redownloaded', 'This Track was just downloaded with the "Redownload metadata" action, and no metadata has been selected since then.'
    AUTOMATICALLY = auto(), 'Selected automatically', 'The metadata for this track has been selected automatically (i.e. without GUI).'
    MANUALLY = auto(), 'Selected manually', 'The metadata for this track has been selected manually (i.e. in the GUI).'


@dataclass
class MusicSyncLibrary:
    path: str = ''
    scripts: set['Script'] = field(default_factory=set)
    metadata_table: pd.DataFrame = field(default_factory=pd.DataFrame)
    children: list[Union['Folder', 'Collection']] = field(default_factory=list)

    @classmethod
    def read_pickle(cls, path: str):
        if path.endswith('.xml'):
            path = path[:-4] + '.pkl'
        with open(path, 'rb') as f:
            return pickle.load(f)

    def write_pickle(self, path: str):
        if path.endswith('.xml'):
            path = path[:-4] + '.pkl'
        with open(path, 'wb') as f:
            pickle.dump(self, f)

    @classmethod
    def read_xml(cls, xml_path: str) -> 'MusicSyncLibrary':
        if xml_path.endswith('.pkl'):
            xml_path = xml_path[:-4] + '.xml'

        tree = et.parse(xml_path)
        root = tree.getroot()
        children = []
        scripts = set()
        for child in root:
            if child.tag == 'Folder':
                children.append(Folder.from_xml(child))
            elif child.tag == 'Collection':
                children.append(Collection.from_xml(child))
            elif child.tag == 'Scripts':
                for script in child:
                    scripts.add(Script.from_xml(script))

        csv_path = xml_path[:-4] + '.csv'
        metadata_table = pd.read_csv(csv_path) if os.path.isfile(csv_path) else pd.DataFrame()

        return cls(path=xml_path, children=children, scripts=scripts, metadata_table=metadata_table)

    def write_xml(self, xml_path: str):
        if xml_path.endswith('.pkl'):
            xml_path = xml_path[:-4] + '.xml'

        root = et.Element('MusicSyncLibrary')
        scripts = et.Element('Scripts')
        for script in self.scripts:
            scripts.append(script.to_xml())
        root.append(scripts)
        for child in self.children:
            root.append(child.to_xml())

        if not xml_path.endswith('.xml'):
            xml_path += '.xml'

        et.ElementTree(root).write(xml_path)

        if not self.metadata_table.empty:
            self.metadata_table.to_csv(xml_path[:-4] + '.csv')

    def __eq__(self, other: MusicSyncLibrary):
        return self.scripts == other.scripts and self.children == other.children and (self.metadata_table == other.metadata_table).all(axis=None)

@dataclass
class Folder(XmlObject):
    name: str
    children: list[Union['Folder', 'Collection']] = field(default_factory=list)

    @classmethod
    def from_xml(cls, el: Element) -> 'Folder':
        children = []
        for child in el:
            if child.tag == 'Folder':
                children.append(Folder.from_xml(child))
            elif child.tag == 'Collection':
                children.append(Collection.from_xml(child))

        return cls(children=children, **el.attrib)

    def to_xml(self) -> Element:
        attrs = vars(self).copy()
        attrs.pop('children')

        el = et.Element('Folder', **attrs)
        for child in self.children:
            el.append(child.to_xml())
        return el


PathComponent = namedtuple('PathComponent', ['id', 'name'])
ScriptReference = namedtuple('ScriptReference', ['name', 'enabled', 'priority'])

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
    # @classproperty
    # def DEFAULT_METADATA_SUGGESTIONS(self) -> list['MetadataField']:
    #     return [
    #         MetadataField('title', suggestions=[
    #             MetadataSuggestion('track'),
    #             MetadataSuggestion('title', split_separators=' - , – , — ,-,|,:,~,‐,_,∙', split_slice='::-1'),
    #             MetadataSuggestion('title', '["“](.+)["“]'),
    #             MetadataSuggestion('title')
    #         ], show_format_options=True, default_format_as_title=True, default_remove_brackets=True),
    #         MetadataField('artist', suggestions=[
    #             MetadataSuggestion('artist', split_separators=r'\,'),
    #             MetadataSuggestion('title', split_separators=' - , – , — ,-,|,:,~,‐,_,∙', ),
    #             MetadataSuggestion('title', ' by (.+)'),
    #             MetadataSuggestion('channel'),
    #             MetadataSuggestion('title')
    #         ], show_format_options=True, default_format_as_title=True, default_remove_brackets=True),
    #         MetadataField('album', suggestions=[
    #             MetadataSuggestion('album'),
    #             MetadataSuggestion('playlist', replace_regex='Album - ', replace_with=''),
    #         ], show_format_options=True, default_format_as_title=True, default_remove_brackets=True),
    #         MetadataField('track', suggestions=[
    #             MetadataSuggestion('track'),
    #             MetadataSuggestion('playlist_index'),
    #         ], enabled=False),
    #         MetadataField('lyrics', suggestions=[
    #             MetadataSuggestion('EXT_LYRICS:%(0:artist,artist&{} - )s%(0:title,track,title)s')
    #         ], enabled=False, timed_data=True),
    #         MetadataField('chapters', suggestions=[
    #             MetadataSuggestion('%(chapters)s+MULTI_VIDEO:%(title)s'),
    #         ], enabled=False, timed_data=True),
    #         MetadataField('thumbnail', suggestions=[
    #             MetadataSuggestion('%(thumbnails.-1.url)s'),
    #             MetadataSuggestion('%(thumbnails.2.url)s'),
    #         ], enabled=False),
    #         MetadataField('timed_data', suggestions=[
    #             MetadataSuggestion('%(0:lyrics)s+%(0:chapters)s'),
    #         ], enabled=False, timed_data=True),
    #     ]

    # @classproperty
    # def DEFAULT_FILE_TAGS(self) -> list['FileTag']:
    #     return [
    #         FileTag('title', '0:title'),
    #         FileTag('artist', '0:artist'),
    #         FileTag('album', '0:album'),
    #         FileTag('thumbnail', '0:thumbnail'),
    #     ]

    DEFAULT_FILENAME_FORMAT: ClassVar[str] = '%(title)s [%(id)s].%(ext)s'
    DEFAULT_URL_NAME_FORMAT: ClassVar[str] = '%(title)s'
    DEFAULT_EXCLUDED_YT_DLP_FIELDS: ClassVar[str] = ('formats, thumbnails, automatic_captions, subtitles, heatmap, '
                                                     'chapters, entries, tags, protocol, http_headers, '
                                                     '_format_sort_fields, _version')

    name: str

    folder_path: str = ''
    filename_format: str = ''
    file_extension: str = ''
    save_playlists_to_subfolders: bool = False
    url_name_format: str = ''
    exclude_after_download: bool = False
    auto_concat_urls: bool = False
    excluded_yt_dlp_fields: str = DEFAULT_EXCLUDED_YT_DLP_FIELDS
    yt_dlp_options: str = ''

    sync_bookmark_file: str = ''
    sync_bookmark_path: list[PathComponent] = field(default_factory=list)
    sync_bookmark_title_as_url_name: bool = False
    sync_delete_files: bool = False

    sync_actions: dict[TrackSyncStatus, TrackSyncAction] = field(default_factory=lambda: Collection.DEFAULT_SYNC_ACTIONS)

    script_settings: list[ScriptReference] = field(default_factory=list)

    urls: list['CollectionUrl'] = field(default_factory=list)

    downloader: 'dl.MusicSyncDownloader | None' = None

    @classmethod
    def from_xml(cls, el: Element) -> 'Collection':
        kwargs: dict[str, Any] = el.attrib.copy()
        kwargs['urls'] = []

        for bool_var in ('save_playlists_to_subfolders', 'sync_bookmark_title_as_url_name', 'sync_delete_files',
                         'exclude_after_download', 'auto_concat_urls'):
            kwargs[bool_var] = kwargs.get(bool_var) == 'True'

        for child in el:
            if child.tag == 'BookmarkSync':
                kwargs['sync_bookmark_file'] = child.attrib['file']
                kwargs['sync_bookmark_title_as_url_name'] = child.attrib['title_as_url_name'] == 'True'
                kwargs['sync_delete_files'] = child.attrib['delete_files'] == 'True'
                kwargs['sync_bookmark_path'] = []
                for path_component in child:
                    kwargs['sync_bookmark_path'].append(PathComponent(**path_component.attrib))
            elif child.tag == 'SyncActions':
                kwargs['sync_actions'] = {TrackSyncStatus(k): TrackSyncAction(v) for k, v in child.attrib.items()}
            elif child.tag == 'CollectionUrl':
                kwargs['urls'].append(CollectionUrl.from_xml(child))
            elif child.tag == 'ScriptSettings':
                kwargs['script_settings'] = []
                for ref in child:
                    if ref.tag == 'ScriptReference':
                        kwargs['script_settings'].append(ScriptReference(ref.attrib['name'], ref.attrib['enabled'] == 'True', int(ref.attrib['priority'])))

        return cls(**kwargs)

    def to_xml(self) -> Element:
        attrs = vars(self).copy()
        for pop_var in ('urls', 'sync_bookmark_file', 'sync_bookmark_path', 'sync_bookmark_title_as_url_name',
                        'sync_delete_files', 'sync_actions', 'script_settings', 'downloader', 'excluded_yt_dlp_fields'):
            attrs.pop(pop_var)

        for str_var in ('save_playlists_to_subfolders', 'exclude_after_download', 'auto_concat_urls'):
            attrs[str_var] = str(attrs[str_var])

        el = et.Element('Collection', **attrs)
        if self.excluded_yt_dlp_fields != Collection.DEFAULT_EXCLUDED_YT_DLP_FIELDS:
            el.attrib['excluded_yt_dlp_fields'] = self.excluded_yt_dlp_fields

        if self.sync_bookmark_file:
            bookmark_sync = et.Element('BookmarkSync', file=self.sync_bookmark_file,
                                       title_as_url_name=str(self.sync_bookmark_title_as_url_name),
                                       delete_files=str(self.sync_delete_files))
            for idx, folder in self.sync_bookmark_path:
                bookmark_sync.append(et.Element('PathComponent', id=idx, name=folder))
            el.append(bookmark_sync)

        if self.sync_actions != Collection.DEFAULT_SYNC_ACTIONS:
            el.append(et.Element('SyncActions', **self.sync_actions))

        if self.script_settings:
            script_settings = et.Element('ScriptSettings')
            for ref in self.script_settings:
                script_settings.append(et.Element('ScriptReference', name=ref.name, enabled=str(ref.enabled), priority=str(ref.priority)))
            el.append(script_settings)

        for url in self.urls:
            el.append(url.to_xml())
        return el

    def add_url(self, url, name, *args, **kwargs):
        self.urls.append(CollectionUrl(url=url, name=name, concat=self.auto_concat_urls, save_to_subfolder=self.save_playlists_to_subfolders, *args, **kwargs))

    def bookmark_sync(self, bookmarks: list[Bookmark]) -> tuple[list, list]:
        occurrences = {}
        local_urls: dict[tuple[str, int], CollectionUrl] = {}

        # build mapping from url, occurrence index -> collection url object
        for url in self.urls:
            occurrences[url.url] = occurrences.get(url.url, 0) + 1
            local_urls[(url.url, occurrences[url.url])] = url

        occurrences = {}
        self.urls = []
        added_urls = []
        for bookmark in bookmarks:
            occurrences[bookmark.url] = occurrences.get(bookmark.url, 0) + 1
            if (bookmark.url, occurrences[bookmark.url]) in local_urls:
                self.urls.append(local_urls.pop((bookmark.url, occurrences[bookmark.url])))
            else:
                self.add_url(url=bookmark.url, name=bookmark.bookmark_title if self.sync_bookmark_title_as_url_name else '')
                added_urls.append((bookmark.url, bookmark.bookmark_title))

        return added_urls, list(local_urls.values())

    def compare(self, progress_callback: Callable[[float, str], None] | None=None, interruption_callback: Callable[[], bool] | None=None) -> pd.DataFrame | Exception:
        self.downloader = dl.MusicSyncDownloader(self)
        assert isinstance(self.downloader, dl.MusicSyncDownloader)  # make ide happy

        try:
            return self.downloader.compare(progress_callback=progress_callback, interruption_callback=interruption_callback)
        except Exception as e:
            return e

    def sync(self, info_df: pd.DataFrame, progress_callback: Callable[[float, str], None] | None=None, interruption_callback: Callable[[], bool] | None=None) -> pd.DataFrame | Exception:
        if self.downloader is None:
            self.downloader = dl.MusicSyncDownloader(self)
        assert isinstance(self.downloader, dl.MusicSyncDownloader)  # make ide happy

        try:
            return self.downloader.sync(info_df, progress_callback=progress_callback, interruption_callback=interruption_callback)
        except Exception as e:
            return e

    def get_real_path(self, url: 'CollectionUrl', track=None):
        folder = self.folder_path
        if self.save_playlists_to_subfolders and url.is_playlist:
            folder = os.path.join(folder, url.name)
        if track is None:
            return folder
        return os.path.join(folder, track.filename)


class YTMusicAlbumCover(PostProcessor):
    # set 1:1 album cover to be embedded (only for yt-music)
    def run(self, info):
        for t in info['thumbnails']:
            if t['id'] == '2':
                info['thumbnail'] = t['url']
                info['thumbnails'] = [t]
                break
        return [], info


@dataclass(order=True)
class CollectionUrl(XmlObject):
    url: str
    name: str = ''
    excluded: bool = False
    concat: bool = False
    save_to_subfolder: bool = False
    is_playlist: bool | None = None
    tracks: pd.DataFrame = field(default_factory=pd.DataFrame)

    def add_track(self, url: str, status: TrackSyncStatus, title: str, filename: str = '', playlist_index: int | None = None,
                  permanently_downloaded: bool = False, metadata_status: MetadataStatus = MetadataStatus.NEW,
                  occurrence_index: int = 1):
        new_track = pd.DataFrame({
            'url': url,
            'status': status,
            'title': title,
            'filename': filename,
            'playlist_index': playlist_index,
            'permanently_downloaded': permanently_downloaded,
            'metadata_status': metadata_status,
            'occurrence_index': occurrence_index,
            'collection_url': self
        }, index=[0])

        self.tracks = pd.concat([self.tracks, new_track], ignore_index=True)
        self.tracks['occurrence_index'] = self.tracks['occurrence_index'].astype(int)

    def get_tracks(self, filter_df: pd.DataFrame) -> pd.DataFrame:
        """
        Filters the given ``filter_df`` dataframe by which tracks of it belong to this collection url. Then filters its own
        tracks dataframe by the tracks present in the ``filter_df`` and returns the result.
        :param filter_df: has to contain the columns ``collection_url``, ``url``, and ``occurrence_index``
        """

        filter_df = filter_df[filter_df['collection_url'].apply(lambda x: x is self)]

        filtered_tracks = self.tracks.merge(filter_df, how='inner', on=['url', 'occurrence_index'], suffixes=(None, '_filter'))

        return filtered_tracks

    def broadcast_update_tracks(self, filter_df: pd.DataFrame, **kwargs) -> pd.DataFrame:
        """
        Filters the given ``filter_df`` dataframe by which tracks of it belong to this collection url. Then filters its own
        tracks dataframe by the tracks present in the ``filter_df`` and updates the key value pairs specified in ``kwargs``
        to all tracks.
        :returns: dataframe containing only modified tracks
        """
        filtered_tracks = self.get_tracks(filter_df)

        for k, v in kwargs.items():
            self.tracks.loc[filtered_tracks.index, k] = v

        return self.tracks.loc[filtered_tracks.index, :]

    def update_track(self, track_url, track_occurrence_index=1, **kwargs):
        if self.tracks.empty:
            self.add_track(url=track_url, occurrence_index=track_occurrence_index, status=TrackSyncStatus.DOWNLOADED, **kwargs)
            return

        track_index = self.tracks[(self.tracks['url'] == track_url) & (self.tracks['occurrence_index'] == track_occurrence_index)].index

        if track_index.empty:
            self.add_track(url=track_url, occurrence_index=track_occurrence_index, status=TrackSyncStatus.DOWNLOADED, **kwargs)
            return

        track_index = track_index[0]
        for k, v in kwargs.items():
            self.tracks.loc[track_index, k] = v

    def remove_tracks(self, filter_df: pd.DataFrame, **kwargs):
        filtered_tracks = self.get_tracks(filter_df)

        self.tracks = self.tracks[~self.tracks.index.isin(filtered_tracks.index)]

    @classmethod
    def from_xml(cls, el: Element) -> 'CollectionUrl':
        track_series: list[pd.Series] = []
        for child in el:
            if child.tag == 'Track':
                track = cls.track_from_xml(child)
                track_series.append(track)

        attrib: dict[str, Any] = el.attrib.copy()

        for bool_var in ('excluded', 'concat', 'save_to_subfolder'):
            attrib[bool_var] = str(attrib.get(bool_var)) == 'True'

        if not 'is_playlist' in attrib or attrib.get('is_playlist') == 'None':
            attrib['is_playlist'] = None
        else:
            attrib['is_playlist'] = attrib.get('is_playlist') == 'True'

        new_collection_url = cls(**attrib)
        tracks = pd.DataFrame(track_series)
        tracks['collection_url'] = new_collection_url
        new_collection_url.tracks = tracks
        return new_collection_url

    def to_xml(self) -> Element:
        attrs = vars(self).copy()
        attrs.pop('tracks')

        for string_var in ('excluded', 'concat', 'is_playlist', 'save_to_subfolder'):
            attrs[string_var] = str(attrs[string_var])

        el = et.Element('CollectionUrl', **attrs)
        for index, track in self.tracks.iterrows():
            el.append(self.track_to_xml(track))
        return el

    @staticmethod
    def track_from_xml(el: Element) -> pd.Series:
        """
        A track Series has to have all attributes defined in Track
        """
        attrib: dict[str, Any] = el.attrib.copy()
        attrib.setdefault('permanently_downloaded', False)
        attrib.setdefault('metadata_status', MetadataStatus.NEW)
        attrib.setdefault('occurrence_index', 1)
        attrib.setdefault('playlist_index', None)

        attrib['status'] = TrackSyncStatus(attrib['status'])
        if isinstance(attrib['metadata_status'], str):
            attrib['metadata_status'] = MetadataStatus(attrib['metadata_status'])
        if isinstance(attrib['permanently_downloaded'], str):
            attrib['permanently_downloaded'] = attrib['permanently_downloaded'] == 'True'
        if isinstance(attrib['occurrence_index'], str):
            attrib['occurrence_index'] = int(attrib['occurrence_index'])
        if isinstance(attrib['playlist_index'], str):
            attrib['playlist_index'] = int(attrib['playlist_index'])

        return pd.Series(attrib)

    @staticmethod
    def track_to_xml(track: pd.Series) -> Element:
        attrs = track.to_dict()
        attrs.pop('collection_url')
        attrs['permanently_downloaded'] = str(attrs['permanently_downloaded'])
        attrs['occurrence_index'] = str(attrs['occurrence_index'])
        if attrs['playlist_index'] is None:
            attrs.pop('playlist_index')
        else:
            attrs['playlist_index'] = str(attrs['playlist_index'])

        return Element('Track', **attrs)

    def __hash__(self):
        return hash(id(self))

    def __eq__(self, other: 'CollectionUrl'):
        attrs = vars(self).copy()
        attrs.pop('tracks')

        other_attrs = vars(other).copy()
        other_attrs.pop('tracks')

        return attrs == other_attrs and (self.tracks.drop(columns=['collection_url']) == other.tracks.drop(columns=['collection_url'])).all(axis=None)


if __name__ == '__main__':
    pass
    # print(MusicSyncLibrary().read_xml('../library.xml').children[0].children[0].update_sync_status())

    # info = {
    #     'ext': 'mp3',
    #     'filepath': 'Mili - TIAN TIAN [Limbus Company] [szyPY8nbBF4].mp3',
    #     'track': 'Test',
    #     'title': 'Mili - TIAN TIAN',
    #     'test': 1.2345
    # }
    # # FFmpegMetadataPP(None).run(info)
    # 
    # info = MetadataParserPP(YoutubeDL(), [(MetadataParserPP.Actions.INTERPRET, '%(title.::-1)s (%(test).2f)',
    #                                        '%(artist)s - %(title)s'),
    #                                       (MetadataParserPP.Actions.REPLACE, 'title', r'\((.+)\)', r'-\1-')]).run(info)
    # 
    # ydl_opts = {'final_ext': 'mp3',
    #             'format': 'ba[acodec^=mp3]/ba/b',
    #             'outtmpl': {'pl_thumbnail': ''},
    #             'writethumbnail': True,
    #             'postprocessors': [{'actions': [(yt_dlp.postprocessor.metadataparser.MetadataParserPP.interpretter,
    #                                              '%(playlist_index)s',
    #                                              '%(meta_track)s'),
    #                                             (yt_dlp.postprocessor.metadataparser.MetadataParserPP.interpretter,
    #                                              '%(thumbnails.2.url)s',
    #                                              '%(thumbnail_test)s')
    #                                             ],
    #                                 'key': 'MetadataParser',
    #                                 'when': 'pre_process'},
    #                                {'key': 'FFmpegExtractAudio',
    #                                 'nopostoverwrites': False,
    #                                 'preferredcodec': 'mp3',
    #                                 'preferredquality': '5'},
    #                                {'add_chapters': True,
    #                                 'add_infojson': 'if_exists',
    #                                 'add_metadata': True,
    #                                 'key': 'FFmpegMetadata'},
    #                                {'already_have_thumbnail': False, 'key': 'EmbedThumbnail'}],
    #             'compat_opts': ['no-youtube-unavailable-videos']
    #             }
    # 
    # ydl = YoutubeDL(ydl_opts)
    # info = ydl.extract_info('https://www.youtube.com/watch?v=53bZSTSLUqI', download=False)
    # pprint(info)
