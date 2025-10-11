import os.path
from collections import namedtuple

import pandas as pd
import yt_dlp

from src.bookmark_library import BookmarkLibrary
from src.music_sync_library import Collection, CollectionUrl, MusicSyncLibrary, Track, TrackSyncStatus, TrackSyncAction

RemoteInfo = namedtuple('RemoteInfo', ['url', 'title', 'playlist_index'])

class MusicSyncDownloader(yt_dlp.YoutubeDL):
    DEFAULT_OPTIONS = {'final_ext': 'mp3',
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


    def __init__(self, params=None, auto_init=True):
        if params is None:
            params = {}
        params = self.DEFAULT_OPTIONS.copy() | params
        super(MusicSyncDownloader, self).__init__(params=params, auto_init=auto_init)

        self.partial_ie_results: dict = {}

    def update_sync_status(self, collection: Collection) -> pd.DataFrame:
        # updating collection urls if sync with bookmarks is enabled
        if collection.sync_bookmark_file:
            bookmarks = BookmarkLibrary.create_from_path(collection.sync_bookmark_file)
            folder = bookmarks.go_to_path([e.id for e in collection.sync_bookmark_path]).get_all_bookmarks()
            collection_urls = [c.url for c in collection.urls]
            for child in folder.values():
                if child.url not in collection_urls:
                    print(f'New url {child.url}, name {child.bookmark_title} added to collection {collection.name}')
                    collection.urls.append(CollectionUrl(url=child.url,
                                                         name=child.bookmark_title if collection.sync_bookmark_title_as_url_name else ''))

        sync_status = pd.DataFrame(columns=['collection', 'url_name', 'file_path', 'track_title', 'status', 'action', 'collection_url', 'track'])

        collection_base_dir = os.listdir(collection.folder_path)

        # download track info of all collection urls
        for coll_url in collection.urls:
            if coll_url.excluded:
                continue

            info = self.extract_info(coll_url.url, process=False)
            if not coll_url.name:
                coll_url.name = self.evaluate_outtmpl(collection.url_name_format or Collection.DEFAULT_URL_NAME_FORMAT, info)
            is_playlist = info.get('_type') == 'playlist'

            if is_playlist:
                entries = list(info['entries'])
                remote_infos = [RemoteInfo(url=e['url'], title=e['title'], playlist_index=str(i)) for i, e in enumerate(entries, start=1)]
                info['entries'] = entries
            else:
                remote_infos = [RemoteInfo(url=info.get('original_url') or info.get('webpage_url'), title=info['title'], playlist_index='')]

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
                    print(f'Local track {local_track.url} not in remote urls')
                    if local_track.status == TrackSyncStatus.DOWNLOADED:
                        # 1. REMOVED_FROM_SOURCE: Track is not present in source, but was present in previous sync
                        local_track.status = TrackSyncStatus.REMOVED_FROM_SOURCE
                    elif local_track.status != TrackSyncStatus.PERMANENTLY_DOWNLOADED:
                        # 2. LOCAL_FILE: File is not in the permanently downloaded files, and does not correspond to a source track
                        local_track.status = TrackSyncStatus.LOCAL_FILE

            for remote_url, remote_title, remote_playlist_index in remote_infos:
                # 3. ADDED_TO_SOURCE: Track is present in source, but was not present in previous sync
                if remote_url not in coll_url.tracks:
                    print(f'Remote url {remote_url} not in coll url')
                    coll_url.tracks[remote_url] = Track(url=remote_url,
                                                   status=TrackSyncStatus.ADDED_TO_SOURCE,
                                                   title=remote_title,
                                                   path=url_folder,
                                                   playlist_index=remote_playlist_index)
                else:
                    local_track: Track = coll_url.tracks[remote_url]
                    if os.path.basename(local_track.path) not in url_folder_contents:
                        # 4. NOT_DOWNLOADED: Track is present in source, was also present in previous sync, but corresponding file does not exist
                        local_track.status = TrackSyncStatus.NOT_DOWNLOADED
                    elif local_track.status != TrackSyncStatus.PERMANENTLY_DOWNLOADED:
                        # 5. DOWNLOADED: Track is present in source and the corresponding file exists
                        local_track.status = TrackSyncStatus.DOWNLOADED
                    # (Implicit) 6. PERMANENTLY_DOWNLOADED: File is present in the permanently downloaded files


            df = pd.DataFrame(data={'collection': [collection.name] * len(coll_url.tracks),
                                    'url_name': [coll_url.name or coll_url.url] * len(coll_url.tracks),
                                    'file_path': [track.path for track in coll_url.tracks.values()],
                                    'track_title': [track.title for track in coll_url.tracks.values()],
                                    'status': [track.status for track in coll_url.tracks.values()],
                                    'action': [collection.sync_actions[track.status] for track in coll_url.tracks.values()],
                                    'collection_url': [coll_url] * len(coll_url.tracks),
                                    'track': coll_url.tracks.values(),
                                    })
            sync_status = pd.concat([sync_status, df]).reset_index(drop=True)

        return sync_status

    def sync(self, info_df: pd.DataFrame):
        # 1. KEEP_PERMANENTLY: mark files as permanently downloaded
        keep_permanently = info_df[info_df['action'] == TrackSyncAction.KEEP_PERMANENTLY]
        for track in keep_permanently['track']:
            track.status = TrackSyncStatus.PERMANENTLY_DOWNLOADED
            track.permanently_downloaded = True

        # 2. REMOVE_FROM_PERMANENTLY_DOWNLOADED: unmark as permanently downloaded
        remove_from_permanently_downloaded = info_df[info_df['action'] == TrackSyncAction.REMOVE_FROM_PERMANENTLY_DOWNLOADED]
        for track in remove_from_permanently_downloaded['track']:
            track.status = TrackSyncStatus.DOWNLOADED
            track.permanently_downloaded = False

        # 3. DELETE: delete files
        delete = info_df[info_df['action'] == TrackSyncAction.DELETE]
        for row in delete[['track', 'collection_url']].itertuples():
            track: Track = row.track
            url: CollectionUrl = row.collection_url
            if os.path.isfile(track.path):
                os.remove(track.path)
            url.tracks.pop(track.url)

        # 4. DOWNLOAD
        download = info_df[info_df['action'] == TrackSyncAction.DOWNLOAD]

        for row in download[['track', 'collection_url']].itertuples():
            pass

        # 5. DO_NOTHING and DECIDE_INDIVIDUALLY are ignored


if __name__ == '__main__':
    library = MusicSyncLibrary.read_xml('../../a.xml')
    collection = library.children[0].children[0]
    downloader = MusicSyncDownloader()

    downloader.update_sync_status(collection)
