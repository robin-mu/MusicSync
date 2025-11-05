import os.path
from collections import namedtuple
from functools import partial
from pprint import pprint
from typing import Callable, Any

import pandas as pd
import yt_dlp

import musicsync.music_sync_library as lib
from .bookmark_library import BookmarkLibrary
from .utils import classproperty, Logger

RemoteInfo = namedtuple('RemoteInfo', ['url', 'title', 'playlist_index'])


class DownloadLogger:
    logger = Logger(prefix='yt-dlp')

    def __init__(self):
        self.interruption_callback: Callable[[], bool] | None = None

    def check_interruption_callback(self):
        if self.interruption_callback is not None and self.interruption_callback():
            raise InterruptedError

    def debug(self, msg: str) -> None:
        self.check_interruption_callback()
        self.logger.debug(msg)

    def info(self, msg: str) -> None:
        self.check_interruption_callback()
        self.logger.info(msg)

    def warning(self, msg: str) -> None:
        self.check_interruption_callback()
        self.logger.warning(msg)


class MusicSyncDownloader(yt_dlp.YoutubeDL):
    @classproperty
    def DEFAULT_OPTIONS(self) -> dict[str, Any]:
        return {'final_ext': 'mp3',
                'format': 'ba[acodec^=mp3]/ba/b',
                'outtmpl': {
                    'default': '%(extractor)s_%(playlist_id)s_%(id)s.%(ext)s',
                    'pl_video': '%(playlist_index)s_%(extractor)s_%(playlist_id)s_%(id)s.%(ext)s',
                },
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
                'logger': DownloadLogger()
                }

    def __init__(self, collection: 'lib.Collection'):
        params = self.DEFAULT_OPTIONS
        params.update({
            'paths': {
                'home': os.path.realpath(collection.folder_path),
            }
        })

        if collection.save_playlists_to_subfolders:
            params['paths']['pl_video'] = f'{os.path.realpath(collection.folder_path)}/%(__musicsync_url_name)s'

        super(MusicSyncDownloader, self).__init__(params=params)

        self.collection: lib.Collection = collection
        self.partial_ie_results: dict = {}
        self.logger = Logger()

    def update_sync_status(self, delete_files: bool = False,
                           progress_callback: Callable[[float, str], None] | None = None,
                           interruption_callback: Callable[[], bool] | None = None):
        """
        Changes the linked collection in-place. It
        - Adds and removes collection urls if bookmark sync is enabled and the bookmark folder has changed. Files are only deleted if delete_files is true
        - Downloads info of all collection urls
        - Updates the sync status of all tracks depending on the downloaded data

        :param delete_files: If true, automatically deletes files belonging to URLs which have been removed from a bookmark-synced folder. If false, only deletes the CollectionUrl object from the collection
        """

        collection = self.collection
        logger = self.logger
        # updating collection urls if sync with bookmarks is enabled
        if collection.sync_bookmark_file:
            logger.prefix = 'bookmark_sync'
            bookmarks = BookmarkLibrary.create_from_path(collection.sync_bookmark_file)
            folder = bookmarks.go_to_path([e.id for e in collection.sync_bookmark_path]).get_all_bookmarks()
            collection_urls = [c.url for c in collection.urls]
            for child in folder.values():
                if child.url not in collection_urls:
                    logger.debug(f'URL {child.url} ({child.bookmark_title}) added to collection "{collection.name}"')
                    collection.urls.append(lib.CollectionUrl(url=child.url,
                                                             name=child.bookmark_title if collection.sync_bookmark_title_as_url_name else '',
                                                             concat=collection.in_auto_concat(child.url)))

            bookmark_urls = [b.url for b in folder.values()]
            to_delete_indexes = []
            for i, collection_url in enumerate(collection.urls):
                if collection_url.url not in bookmark_urls:
                    logger.debug(
                        f'URL {collection_url.url} ({collection_url.name}) removed from collection "{collection.name}"')
                    to_delete_indexes.append(i)

                    if delete_files:
                        if collection_url.is_playlist is None:
                            logger.debug(
                                f'Removed URL {collection_url.url} has never been synced, so no files can be deleted.')
                            continue
                        folder = self.collection.get_real_path(collection_url)
                        for track in collection_url.tracks.values():
                            filename = self.collection.get_real_path(collection_url, track)
                            logger.info(f'Deleting file {filename}.')
                            if os.path.isfile(filename):
                                os.remove(filename)

                        if len(os.listdir(folder)) == 0:
                            logger.info(f'Deleting empty folder {folder}.')
                            if os.path.isdir(folder):
                                os.remove(folder)

            collection.urls = [collection_url for i, collection_url in enumerate(collection.urls) if
                               i not in to_delete_indexes]

        # download track info of all collection urls
        self.params['logger'].interruption_callback = interruption_callback
        logger.prefix = 'update_sync_status'
        for (i, coll_url) in enumerate(collection.urls):
            logger.reset_indent()

            if progress_callback is not None:
                if coll_url.name:
                    progress_text = f'"{coll_url.name}" ({coll_url.url})'
                else:
                    progress_text = f'{coll_url.url}'
                progress_callback(i / len(collection.urls),
                                  f'Downloading info for {progress_text} [{i + 1}/{len(collection.urls)}]')

            if coll_url.excluded:
                logger.debug(f'{coll_url} is excluded. Skipping...')
                continue

            coll_url.concat = self.collection.in_auto_concat(coll_url.url)

            info = self.extract_info(coll_url.url, process=False)
            if not coll_url.name:
                coll_url.name = self.evaluate_outtmpl(
                    collection.url_name_format or lib.Collection.DEFAULT_URL_NAME_FORMAT,
                    info)

            is_playlist = info.get('_type') == 'playlist'
            coll_url.is_playlist = is_playlist
            if is_playlist:
                entries = list(info['entries'])
                remote_infos = [RemoteInfo(url=e['url'], title=e['title'], playlist_index=str(i)) for i, e in
                                enumerate(entries, start=1)]
                info['entries'] = entries
            else:
                remote_infos = [RemoteInfo(url=info.get('original_url') or info['webpage_url'], title=info['title'],
                                           playlist_index='')]

            logger.debug(f'Processing URL {coll_url.url} ({coll_url.name})')
            logger.debug(f'Playlist: {"yes" if coll_url.is_playlist else "no"}')

            self.partial_ie_results[coll_url.url] = info

            url_folder = self.collection.get_real_path(coll_url)
            url_folder_contents = os.listdir(url_folder) if os.path.isdir(url_folder) else []

            logger.debug(f'Folder: {url_folder}')
            logger.indent()

            remote_urls = [info.url for info in remote_infos]
            for local_track in coll_url.tracks.values():
                if local_track.url not in remote_urls:
                    if local_track.status == lib.TrackSyncStatus.DOWNLOADED:
                        # 1. REMOVED_FROM_SOURCE: Track is not present in source, but was present in previous sync
                        local_track.status = lib.TrackSyncStatus.REMOVED_FROM_SOURCE
                    elif local_track.status != lib.TrackSyncStatus.PERMANENTLY_DOWNLOADED:
                        # 2. LOCAL_FILE: File is not in the permanently downloaded files, and does not correspond to a source track
                        local_track.status = lib.TrackSyncStatus.LOCAL_FILE

                    logger.debug(
                        f'{local_track.url} ({local_track.filename}): Not in URL tracks and marked as {local_track.status}')

            for remote_track_url, remote_title, remote_playlist_index in remote_infos:
                # 3. ADDED_TO_SOURCE: Track is present in source, but was not present in previous sync
                if remote_track_url not in coll_url.tracks:
                    logger.debug(f'{remote_track_url} ({remote_title}): {lib.TrackSyncStatus.ADDED_TO_SOURCE}.')

                    coll_url.tracks[remote_track_url] = lib.Track(url=remote_track_url,
                                                                  status=lib.TrackSyncStatus.ADDED_TO_SOURCE,
                                                                  title=remote_title,
                                                                  filename='',
                                                                  playlist_index=remote_playlist_index)
                else:
                    local_track: lib.Track = coll_url.tracks[remote_track_url]
                    if local_track.filename not in url_folder_contents:
                        # 4. NOT_DOWNLOADED: Track is present in source, was also present in previous sync, but corresponding file does not exist
                        logger.debug(
                            f'{remote_track_url} ({remote_title}): File {local_track.filename} does not exist. Marked as {lib.TrackSyncStatus.NOT_DOWNLOADED}')

                        local_track.status = lib.TrackSyncStatus.NOT_DOWNLOADED
                    elif local_track.status != lib.TrackSyncStatus.PERMANENTLY_DOWNLOADED:
                        # 5. DOWNLOADED: Track is present in source and the corresponding file exists
                        logger.debug(f'{remote_track_url} ({remote_title}): {lib.TrackSyncStatus.DOWNLOADED}')
                        local_track.status = lib.TrackSyncStatus.DOWNLOADED
                    # (Implicit) 6. PERMANENTLY_DOWNLOADED: File is present in the permanently downloaded files

    def sync(self, info_df: pd.DataFrame, progress_callback: Callable[[float, str], None] | None = None,
             interruption_callback: Callable[[], bool] | None = None) -> pd.DataFrame:
        """
        Changes the linked collection in-place, depending on the given ``info_df``.
        :param info_df: Info DataFrame. Has to contain the following columns:
            collection_url: The CollectionUrl object
            track: The Track object
            action: The selected TrackSyncAction for this track

        This function

        - Changes the status of all tracks with an action of ``KEEP_PERMANENTLY`` to ``PERMANENTLY_DOWNLOADED``
        - Changes the status of all tracks with an action of ``REMOVE_FROM_PERMANENTLY_DOWNLOADED`` to ``DOWNLOADED``
        - Deletes all files and removes the ``Track`` object from the ``CollectionUrl`` for all tracks with an action of ``DELETE``
        - Downloads all tracks with an action of ``DOWNLOAD`` and
            - adds playlist information to the ``Track`` object

        :return: A dataframe containing all not excluded metadata from all downloaded tracks.
        """

        logger = self.logger
        logger.prefix = 'sync'
        logger.reset_indent()

        # 1. KEEP_PERMANENTLY: mark files as permanently downloaded
        keep_permanently = info_df[info_df['action'] == lib.TrackSyncAction.KEEP_PERMANENTLY]

        if len(keep_permanently) > 0:
            logger.debug(f'KEEP_PERMANENTLY: {len(keep_permanently)} tracks.')
            logger.indent()

        for track in keep_permanently['track']:
            track.status = lib.TrackSyncStatus.PERMANENTLY_DOWNLOADED
            track.permanently_downloaded = True

            logger.debug(f'{track.url} ({track.filename}) marked as {track.status}')

        logger.reset_indent()

        # 2. REMOVE_FROM_PERMANENTLY_DOWNLOADED: unmark as permanently downloaded
        remove_from_permanently_downloaded = info_df[
            info_df['action'] == lib.TrackSyncAction.REMOVE_FROM_PERMANENTLY_DOWNLOADED]

        if len(remove_from_permanently_downloaded) > 0:
            logger.debug(f'REMOVE_FROM_PERMANENTLY_DOWNLOADED: {len(remove_from_permanently_downloaded)} tracks.')
            logger.indent()

        for track in remove_from_permanently_downloaded['track']:
            track.status = lib.TrackSyncStatus.DOWNLOADED
            track.permanently_downloaded = False

            logger.debug(f'{track.url} ({track.filename}) marked as {track.status}')

        logger.reset_indent()

        # 3. DELETE: delete files
        delete = info_df[info_df['action'] == lib.TrackSyncAction.DELETE]

        if len(delete) > 0:
            logger.info(f'DELETE: {len(delete)} tracks.')
            logger.indent()

        for row in delete[['track', 'collection_url']].itertuples():
            track: lib.Track = row.track
            url: lib.CollectionUrl = row.collection_url
            path = self.collection.get_real_path(url, track)

            if os.path.isfile(path):
                os.remove(path)
                logger.info(f'Deleting {track.filename} ({track.url})')
            else:
                logger.info(f'Could not delete file {track.filename} ({track.url}) because it does not exist')

            url.tracks.pop(track.url)

        logger.reset_indent()

        # 4. REDOWNLOAD_METADATA and DOWNLOAD
        def filter_redownloaded(info_dict, url: lib.CollectionUrl, entries_df: pd.DataFrame, metadata_df: pd.DataFrame) -> str | None:
            pprint(info_dict)

        download = info_df[(info_df['action'] == lib.TrackSyncAction.REDOWNLOAD_METADATA) | (
                    info_df['action'] == lib.TrackSyncAction.DOWNLOAD)]

        if len(download) > 0:
            logger.debug(f'DOWNLOAD or REDOWNLOAD_METADATA: {len(download)} tracks.')
            logger.indent()

        groupby_url = download.groupby('collection_url')

        metadata_df = pd.DataFrame()
        for url in groupby_url.groups:
            group = groupby_url.get_group(url)
            entries = pd.DataFrame({'track': group['track'], 'action': group['action']})
            entries.index = pd.Index(group['track'].apply(lambda t: t.playlist_index), name='playlist_index')

            if url.is_playlist:
                self.params['playlist_items'] = ','.join(entries.index.tolist())

            self.params['match_filter'] = partial(filter_redownloaded, url=url, entries_df=entries, metadata_df=metadata_df)

            if url.url in self.partial_ie_results:
                info = self.process_ie_result(self.partial_ie_results[url.url])
                self.partial_ie_results.pop(url.url)
            else:
                info = self.extract_info(url.url)




        # 5. DO_NOTHING and DECIDE_INDIVIDUALLY are ignored


if __name__ == '__main__':
    library = lib.MusicSyncLibrary.read_xml('../a.xml')
    c = library.children[0].children[0]
    downloader = MusicSyncDownloader(c)

    downloader.update_sync_status()
