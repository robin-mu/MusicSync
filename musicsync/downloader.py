import os.path
from collections import namedtuple
from functools import partial
from typing import Callable, Any, cast

import pandas as pd
import yt_dlp
from yt_dlp.postprocessor import FFmpegConcatPP
from yt_dlp.postprocessor.common import PostProcessor

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

    def error(self, msg: str) -> None:
        self.check_interruption_callback()
        self.logger.error(msg)

    def indent(self, by: int):
        self.logger.indent(by)

    def reset_indent(self):
        self.logger.reset_indent()


class MusicSyncPreProcessor(PostProcessor):
    def __init__(self, downloader=None):
        super().__init__(downloader)

    def run(self, info):
        #print(info)
        if self._downloader.current_url.concat and info.get('_type') == 'playlist':
            print('playlist')
            info['_type'] = 'multi_video'

        return [], info

class MusicSyncPostProcessor(PostProcessor):
    def __init__(self, downloader=None):
        super().__init__(downloader)

    def run(self, info):
        info['__finaldir'] = self._downloader.collection.get_real_path(self._downloader.current_url)

        return [], info


class MusicSyncDownloader(yt_dlp.YoutubeDL):
    @classproperty
    def DEFAULT_OPTIONS(self) -> dict[str, Any]:
        return {'outtmpl': {
                    'default': '%(extractor)s_%(playlist_id&{}_|)s%(playlist_index&{}_|)s%(id)s.%(ext)s',
                },
                'postprocessors': [
                    {'actions': [(yt_dlp.postprocessor.metadataparser.MetadataParserPP.interpretter,
                                  '%(playlist_index)s',
                                  '%(meta_track)s')],
                     'key': 'MetadataParser',
                     'when': 'pre_process'},
                    {'add_chapters': True,
                     'add_infojson': 'if_exists',
                     'add_metadata': True,
                     'key': 'FFmpegMetadata'}],
                'compat_opts': ['no-youtube-unavailable-videos'],
                'ignoreerrors': False,
                'logger': DownloadLogger(),
                }

    def __init__(self, collection: 'lib.Collection'):
        params = self.DEFAULT_OPTIONS
        params.update({
            'paths': {
                'home': os.path.realpath(collection.folder_path),
            }
        })

        if collection.filename_format:
            params['outtmpl']['default'] = collection.filename_format

        # TODO: if file extension is audio, extract audio
        if True:
            params['postprocessors'].append({
                'key': 'FFmpegExtractAudio',
                'nopostoverwrites': False,
                'preferredcodec': collection.file_extension or 'best',
                'preferredquality': '5'
            })

            params['format'] = 'ba/b'

        super(MusicSyncDownloader, self).__init__(params=params)

        self.collection: lib.Collection = collection
        self.partial_ie_results: dict = {}
        self.logger = Logger()

        self.current_url: lib.CollectionUrl | None = None

        self.add_post_processor(MusicSyncPreProcessor(downloader=self), when='playlist')
        self.add_post_processor(FFmpegConcatPP(downloader=self, only_multi_video=True), when='playlist')
        self.add_post_processor(MusicSyncPostProcessor(downloader=self), when='post_process')

    def compare(self, delete_files: bool = False,
                progress_callback: Callable[[float, str], None] | None = None,
                interruption_callback: Callable[[], bool] | None = None) -> pd.DataFrame:
        """
        Changes the linked collection in-place. It

        - Adds, removes and reorders collection urls if bookmark sync is enabled and the bookmark folder has changed. Files are only deleted if delete_files is true
        - Downloads info of all collection urls (without processing)

        :param delete_files: If true, automatically deletes files belonging to URLs which have been removed from a bookmark-synced folder. If false, only deletes the CollectionUrl object from the collection

        :return: Dataframe containing the updated data (video name, playlist index, sync status, ...) of all tracks in all collection urls
        """

        collection = self.collection
        logger = self.logger
        # updating collection urls if sync with bookmarks is enabled
        if collection.sync_bookmark_file:
            logger.prefix = 'bookmark_sync'
            bookmarks = BookmarkLibrary.create_from_path(collection.sync_bookmark_file)
            folder = bookmarks.go_to_path([e.id for e in collection.sync_bookmark_path]).get_all_bookmarks()

            added_urls, removed_urls = collection.bookmark_sync(list(folder.values()))

            for url, name in added_urls:
                logger.debug(f'URL {url} ({name}) added to collection "{collection.name}"')

            for collection_url in removed_urls:
                logger.debug(f'URL {collection_url.url} ({collection_url.name}) removed from collection "{collection.name}"')

                if delete_files:
                    if collection_url.is_playlist is None:
                        logger.debug(f'Removed URL {collection_url.url} has never been synced, so no files can be deleted.')
                        continue
                    folder = self.collection.get_real_path(collection_url)
                    for track in collection_url.tracks.itertuples():
                        filename = self.collection.get_real_path(collection_url, track)
                        logger.info(f'Deleting file {filename}.')
                        if os.path.isfile(filename):
                            os.remove(filename)

                    if len(os.listdir(folder)) == 0:
                        logger.info(f'Deleting empty folder {folder}.')
                        if os.path.isdir(folder):
                            os.remove(folder)

        # download track info of all collection urls
        self.params['logger'].interruption_callback = interruption_callback
        logger.prefix = 'compare'

        df = pd.DataFrame()
        for i, collection_url in enumerate(collection.urls):
            logger.reset_indent()

            if progress_callback is not None:
                if collection_url.name:
                    progress_text = f'"{collection_url.name}" ({collection_url.url})'
                else:
                    progress_text = f'{collection_url.url}'
                progress_callback(i / len(collection.urls),
                                  f'Downloading info for {progress_text} [{i + 1}/{len(collection.urls)}]')

            if collection_url.excluded:
                logger.debug(f'{collection_url} is excluded. Skipping...')
                continue

            info = self.extract_info(collection_url.url, process=False)
            if not collection_url.name:
                collection_url.name = self.evaluate_outtmpl(
                    collection.url_name_format or lib.Collection.DEFAULT_URL_NAME_FORMAT,
                    info)

            is_playlist = info.get('_type') == 'playlist'
            collection_url.is_playlist = is_playlist
            if is_playlist:
                entries = list(info['entries'])
                videos = pd.DataFrame({
                    'url': [e['url'] for e in entries],
                    'title': [e['title'] for e in entries],
                    'playlist_index': list(range(1, len(entries) + 1)),
                    'occurrence_index': 1,
                })

                # count number of occurrences of every url
                occurrences = {}
                for row in videos.itertuples():
                    occurrences[row.url] = occurrences.get(row.url, 0) + 1
                    videos.loc[row.Index, 'occurrence_index'] = occurrences[row.url]

                info['entries'] = entries
            else:
                videos = pd.DataFrame({
                    'url': info.get('original_url') or info['webpage_url'],
                    'title': info['title'],
                    'playlist_index': None,
                    'occurrence_index': 1,
                }, index=[0])


            logger.debug(f'Processing URL {collection_url.url} ({collection_url.name})')
            logger.debug(f'Playlist: {"yes" if collection_url.is_playlist else "no"}')

            self.partial_ie_results[collection_url.url] = info

            url_folder = self.collection.get_real_path(collection_url)
            url_folder_contents = os.listdir(url_folder) if os.path.isdir(url_folder) else []

            logger.debug(f'Folder: {url_folder}')
            logger.indent()

            occurrences = {}
            tracks = {}
            # build mapping from url, occurrence index -> track namedtuple from the tracks dataframe
            for track in collection_url.tracks.itertuples():
                occurrences[track.url] = occurrences.get(track.url, 0) + 1
                tracks[(track.url, occurrences[track.url])] = track

            status_df = pd.DataFrame()
            for video in videos.itertuples():
                matched_track = tracks.get((video.url, video.occurrence_index))

                if matched_track:
                    matched_track_dict = matched_track._asdict() | video._asdict()  # Update track with new video info (name, playlist index)
                    matched_track_dict.pop('Index')

                    if matched_track.filename not in url_folder_contents:
                        # 4. NOT_DOWNLOADED: Track is present in source, was also present in previous sync, but corresponding file does not exist
                        logger.debug(
                            f'{video.url} ({video.title}): File {matched_track.filename} does not exist. Marked as {lib.TrackSyncStatus.NOT_DOWNLOADED}')

                        matched_track_dict['status'] = lib.TrackSyncStatus.NOT_DOWNLOADED
                    elif matched_track.status != lib.TrackSyncStatus.PERMANENTLY_DOWNLOADED:
                        # 5. DOWNLOADED: Track is present in source and the corresponding file exists
                        logger.debug(f'{video.url} ({video.title}): {lib.TrackSyncStatus.DOWNLOADED}')
                        matched_track_dict['status'] = lib.TrackSyncStatus.DOWNLOADED
                    # (Implicit) 6. PERMANENTLY_DOWNLOADED: File is present in the permanently downloaded files

                    new_track = pd.DataFrame(matched_track_dict, index=[0])
                    tracks.pop((video.url, video.occurrence_index))
                else:
                    # 3. ADDED_TO_SOURCE: Track is present in source, but was not present in previous sync
                    logger.debug(f'{video.url} ({video.title}): {lib.TrackSyncStatus.ADDED_TO_SOURCE}.')

                    new_track = pd.DataFrame({
                        'url': video.url,
                        'status': lib.TrackSyncStatus.ADDED_TO_SOURCE,
                        'title': video.title,
                        'filename': '',
                        'playlist_index': video.playlist_index,
                        'permanently_downloaded': False,
                        'metadata_status': lib.MetadataStatus.NEW,
                        'occurrence_index': video.occurrence_index,
                        'collection_url': collection_url,
                    }, index=[0])

                status_df = pd.concat([status_df, new_track], ignore_index=True)

            # Determine status for remaining tracks from the collection url
            for track in tracks.values():
                track_dict = track._asdict()
                track_dict.pop('Index')
                if track.status == lib.TrackSyncStatus.DOWNLOADED:
                    # 1. REMOVED_FROM_SOURCE: Track is not present in source, but was present in previous sync
                    track_dict['status'] = lib.TrackSyncStatus.REMOVED_FROM_SOURCE
                elif track.status != lib.TrackSyncStatus.PERMANENTLY_DOWNLOADED:
                    # 2. LOCAL_FILE: File is not in the permanently downloaded files, and does not correspond to a source track
                    track_dict['status'] = lib.TrackSyncStatus.LOCAL_FILE

                logger.debug(
                    f'{track.url} ({track.filename}): Not in URL tracks and marked as {track_dict["status"]}')

                new_track = pd.DataFrame(track_dict, index=[0])
                status_df = pd.concat([status_df, new_track], ignore_index=True)

            df = pd.concat([df, status_df], ignore_index=True)

        return df


    def sync(self, info_df: pd.DataFrame, progress_callback: Callable[[float, str], None] | None = None,
             interruption_callback: Callable[[], bool] | None = None) -> pd.DataFrame:
        """
        Changes the linked collection in-place, depending on the given ``info_df``.
        :param info_df: Info DataFrame. Has to contain the following columns:
            collection_url: The ``CollectionUrl`` object
            url: The video URL
            occurrence_index: The video occurrence index in that Collection URL
            action: The selected TrackSyncAction for this video

        This function

        - Changes the status of all tracks with an action of ``KEEP_PERMANENTLY`` to ``PERMANENTLY_DOWNLOADED``
        - Changes the status of all tracks with an action of ``REMOVE_FROM_PERMANENTLY_DOWNLOADED`` to ``DOWNLOADED``
        - Deletes all files and removes the Track object from the ``CollectionUrl`` for all tracks with an action of ``DELETE``
        - Downloads all tracks with an action of ``DOWNLOAD`` and
            - adds playlist information to the ``Track`` object

        :return: A dataframe containing all metadata from all downloaded tracks.
        """

        logger = self.logger
        logger.prefix = 'sync'
        logger.reset_indent()

        # 1. KEEP_PERMANENTLY: mark files as permanently downloaded
        keep_permanently = info_df[info_df['action'] == lib.TrackSyncAction.KEEP_PERMANENTLY]

        if len(keep_permanently) > 0:
            logger.debug(f'KEEP_PERMANENTLY: {len(keep_permanently)} tracks.')
            logger.indent()

        for collection_url in keep_permanently['collection_url'].unique():
            modified = collection_url.update_tracks(keep_permanently, status=lib.TrackSyncStatus.PERMANENTLY_DOWNLOADED)

            for track in modified.itertuples():
                logger.debug(f'{track.url} ({track.filename}) marked as {track.status}')

        logger.reset_indent()

        # 2. REMOVE_FROM_PERMANENTLY_DOWNLOADED: unmark as permanently downloaded
        remove_from_permanently_downloaded = info_df[
            info_df['action'] == lib.TrackSyncAction.REMOVE_FROM_PERMANENTLY_DOWNLOADED]

        if len(remove_from_permanently_downloaded) > 0:
            logger.debug(f'REMOVE_FROM_PERMANENTLY_DOWNLOADED: {len(remove_from_permanently_downloaded)} tracks.')
            logger.indent()

        for collection_url in remove_from_permanently_downloaded['collection_url'].unique():
            modified = collection_url.update_tracks(remove_from_permanently_downloaded,
                                                    status=lib.TrackSyncStatus.DOWNLOADED)

            for track in modified.itertuples():
                logger.debug(f'{track.url} ({track.filename}) marked as {track.status}')

        logger.reset_indent()

        # # 3. DELETE: delete files
        # delete = info_df[info_df['action'] == lib.TrackSyncAction.DELETE]
        #
        # if len(delete) > 0:
        #     logger.info(f'DELETE: {len(delete)} tracks.')
        #     logger.indent()
        #     self.params['logger'].indent(2)
        #
        # for row in delete[['track', 'collection_url']].itertuples():
        #     track = row.track
        #     url: lib.CollectionUrl = cast(lib.CollectionUrl, cast(object, row.collection_url))
        #     path = self.collection.get_real_path(url, track)
        #
        #     if os.path.isfile(path):
        #         os.remove(path)
        #         logger.info(f'Deleting {track.filename} ({track.url})')
        #     else:
        #         logger.info(f'Could not delete file {track.filename} ({track.url}) because it does not exist')
        #
        #     url.tracks.pop(track.url)
        #
        # logger.reset_indent()

        # 4. REDOWNLOAD_METADATA and DOWNLOAD
        def filter_redownloaded(info_dict, url: lib.CollectionUrl, actions_df: pd.DataFrame) -> str | None:
            info_dicts.append(info_dict)

            if actions_df.loc[str(info_dict.get('playlist_index', '')), 'action'] == lib.TrackSyncAction.REDOWNLOAD_METADATA:
                return "Skipping download since sync action is set to REDOWNLOAD_METADATA"

            return None

        download = info_df[(info_df['action'] == lib.TrackSyncAction.REDOWNLOAD_METADATA) | (
                    info_df['action'] == lib.TrackSyncAction.DOWNLOAD)]

        if len(download) > 0:
            logger.debug(f'DOWNLOAD or REDOWNLOAD_METADATA: {len(download)} tracks.')
            logger.indent()
            self.params['logger'].indent(2)

        info_dicts = []
        print(self.collection.urls)
        print(download['collection_url'].unique().tolist())
        for collection_url in download['collection_url'].unique():
            self.current_url = collection_url
            print(download[download['collection_url'].apply(lambda x: x is collection_url)][['url', 'occurrence_index']])

            tracks = collection_url.get_tracks(download)
            actions = pd.DataFrame({'action': tracks['action']})
            actions.index = pd.Index(tracks['playlist_index'], name='playlist_index')

            if collection_url.is_playlist:
                self.params['playlist_items'] = ','.join(actions.index.tolist())

            self.params['match_filter'] = partial(filter_redownloaded, url=collection_url, actions_df=actions)

            if collection_url.url in self.partial_ie_results:
                logger.debug(f'Processing IE result for URL {collection_url.url}')
                info = self.process_ie_result(self.partial_ie_results[collection_url.url])
                self.partial_ie_results.pop(collection_url.url)
            else:
                logger.debug(f'Extracting URL {collection_url.url}')
                info = self.extract_info(collection_url.url)

            info_dicts.append(info)

            # TODO: add tracks from info_df to collection url tracks

        metadata_df = pd.DataFrame.from_records(info_dicts)
        metadata_df.to_csv('test.csv')


        # 5. DO_NOTHING and DECIDE_INDIVIDUALLY are ignored


if __name__ == '__main__':
    library = lib.MusicSyncLibrary.read_xml('../a.xml')
    c = library.children[0].children[0]
    downloader = MusicSyncDownloader(c)

    downloader.compare()
