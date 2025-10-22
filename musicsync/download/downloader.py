import logging
import os.path
from collections import namedtuple
from typing import Callable, Any

import pandas as pd
import yt_dlp

from bookmark_library import BookmarkLibrary
from utils import log_msg, classproperty
import music_sync_library as lib

RemoteInfo = namedtuple('RemoteInfo', ['url', 'title', 'playlist_index'])
logger = logging.getLogger('MusicSync')


class MusicSyncDownloader(yt_dlp.YoutubeDL):
    @classproperty
    def DEFAULT_OPTIONS(self) -> dict[str, Any]:
        return {'final_ext': 'mp3',
                'format': 'ba[acodec^=mp3]/ba/b',
                'outtmpl': {'pl_thumbnail': ''},
                'writethumbnail': True,
                'postprocessors': [
                    {'actions': [(yt_dlp.postprocessor.metadataparser.MetadataParserPP.interpretter,
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
                'compat_opts': ['no-youtube-unavailable-videos'],
                'quiet': True
                }

    def __init__(self, collection: 'lib.Collection'):
        params = self.DEFAULT_OPTIONS
        super(MusicSyncDownloader, self).__init__(params=params)

        self.collection = collection
        self.partial_ie_results: dict = {}

    def update_sync_status(self, progress_callback: Callable | None = None):
        """
        Changes the linked collection in-place. It
        - Adds and removes collection urls if bookmark sync is enabled and the bookmark folder has changed
        - Downloads info of all collection urls
        - Updates the sync status of all tracks depending on the downloaded data
        """

        collection = self.collection
        # updating collection urls if sync with bookmarks is enabled
        if collection.sync_bookmark_file:
            bookmarks = BookmarkLibrary.create_from_path(collection.sync_bookmark_file)
            folder = bookmarks.go_to_path([e.id for e in collection.sync_bookmark_path]).get_all_bookmarks()
            collection_urls = [c.url for c in collection.urls]
            for child in folder.values():
                if child.url not in collection_urls:
                    logger.debug(
                        log_msg(f'Url {child.url} ({child.bookmark_title}) added to collection {collection.name}',
                                'bookmark_sync'))
                    collection.urls.append(lib.CollectionUrl(url=child.url,
                                                         name=child.bookmark_title if collection.sync_bookmark_title_as_url_name else ''))

            bookmark_urls = [b.url for b in folder.values()]
            to_delete_indexes = []
            for i, collection_url in enumerate(collection.urls):
                if collection_url.url not in bookmark_urls:
                    logger.debug(log_msg(
                        f'Url {collection_url.url} ({collection_url.name} removed from collection {collection.name}',
                        'bookmark_sync'))
                    to_delete_indexes.append(i)

                    # TODO delete tracks

            collection.urls = [collection_url for i, collection_url in enumerate(collection.urls) if
                               i not in to_delete_indexes]

        collection_base_dir = os.listdir(collection.folder_path) if os.path.exists(collection.folder_path) else []

        # download track info of all collection urls
        for coll_url in collection.urls:
            if coll_url.excluded:
                logger.debug(log_msg(f'{coll_url} is excluded', 'download'))
                continue

            logger.debug(log_msg(f'Downloading {coll_url}', 'download'))
            info = self.extract_info(coll_url.url, process=False)
            if not coll_url.name:
                coll_url.name = self.evaluate_outtmpl(collection.url_name_format or lib.Collection.DEFAULT_URL_NAME_FORMAT,
                                                      info)

            is_playlist = info.get('_type') == 'playlist'
            if is_playlist:
                entries = list(info['entries'])
                remote_infos = [RemoteInfo(url=e['url'], title=e['title'], playlist_index=str(i)) for i, e in
                                enumerate(entries, start=1)]
                info['entries'] = entries
            else:
                remote_infos = [RemoteInfo(url=info.get('original_url') or info.get('webpage_url'), title=info['title'],
                                           playlist_index='')]

            self.partial_ie_results[coll_url.url] = info

            if collection.save_playlists_to_subfolders and is_playlist:
                url_folder = os.path.join(collection.folder_path, coll_url.name)
                url_folder_contents = os.listdir(url_folder) if os.path.isdir(url_folder) else []
            else:
                url_folder = collection.folder_path
                url_folder_contents = collection_base_dir

            remote_urls = [info.url for info in remote_infos]
            for local_track in coll_url.tracks.values():
                if local_track.url not in remote_urls:
                    logger.debug(f'Local track {local_track.url} not in remote urls')
                    if local_track.status == lib.TrackSyncStatus.DOWNLOADED:
                        # 1. REMOVED_FROM_SOURCE: Track is not present in source, but was present in previous sync
                        local_track.status = lib.TrackSyncStatus.REMOVED_FROM_SOURCE
                    elif local_track.status != lib.TrackSyncStatus.PERMANENTLY_DOWNLOADED:
                        # 2. LOCAL_FILE: File is not in the permanently downloaded files, and does not correspond to a source track
                        local_track.status = lib.TrackSyncStatus.LOCAL_FILE

            for remote_url, remote_title, remote_playlist_index in remote_infos:
                # 3. ADDED_TO_SOURCE: Track is present in source, but was not present in previous sync
                if remote_url not in coll_url.tracks:
                    logger.debug(f'Remote url {remote_url} not in collection url tracks')
                    coll_url.tracks[remote_url] = lib.Track(url=remote_url,
                                                            status=lib.TrackSyncStatus.ADDED_TO_SOURCE,
                                                            title=remote_title,
                                                            filename='',
                                                            playlist_index=remote_playlist_index)
                else:
                    local_track: lib.Track = coll_url.tracks[remote_url]
                    if local_track.filename not in url_folder_contents:
                        # 4. NOT_DOWNLOADED: Track is present in source, was also present in previous sync, but corresponding file does not exist
                        local_track.status = lib.TrackSyncStatus.NOT_DOWNLOADED
                    elif local_track.status != lib.TrackSyncStatus.PERMANENTLY_DOWNLOADED:
                        # 5. DOWNLOADED: Track is present in source and the corresponding file exists
                        local_track.status = lib.TrackSyncStatus.DOWNLOADED
                    # (Implicit) 6. PERMANENTLY_DOWNLOADED: File is present in the permanently downloaded files

    def sync(self, info_df: pd.DataFrame):
        # 1. KEEP_PERMANENTLY: mark files as permanently downloaded
        keep_permanently = info_df[info_df['action'] == lib.TrackSyncAction.KEEP_PERMANENTLY]
        for track in keep_permanently['track']:
            track.status = lib.TrackSyncStatus.PERMANENTLY_DOWNLOADED
            track.permanently_downloaded = True

        # 2. REMOVE_FROM_PERMANENTLY_DOWNLOADED: unmark as permanently downloaded
        remove_from_permanently_downloaded = info_df[
            info_df['action'] == lib.TrackSyncAction.REMOVE_FROM_PERMANENTLY_DOWNLOADED]
        for track in remove_from_permanently_downloaded['track']:
            track.status = lib.TrackSyncStatus.DOWNLOADED
            track.permanently_downloaded = False

        # 3. DELETE: delete files
        delete = info_df[info_df['action'] == lib.TrackSyncAction.DELETE]
        for row in delete[['track', 'collection_url']].itertuples():
            track: lib.Track = row.track
            url: lib.CollectionUrl = row.collection_url
            path = self.collection.folder_path
            if self.collection.save_playlists_to_subfolders:
                path = os.path.join(path, url.name)
            path = os.path.join(path, track.filename)

            if os.path.isfile(path):
                os.remove(path)
            url.tracks.pop(track.url)

        # 4. DOWNLOAD
        download = info_df[info_df['action'] == lib.TrackSyncAction.DOWNLOAD]

        for row in download[['track', 'collection_url']].itertuples():
            pass

        # 5. DO_NOTHING and DECIDE_INDIVIDUALLY are ignored


if __name__ == '__main__':
    library = lib.MusicSyncLibrary.read_xml('../../a.xml')
    c = library.children[0].children[0]
    downloader = MusicSyncDownloader(c)

    downloader.update_sync_status()
