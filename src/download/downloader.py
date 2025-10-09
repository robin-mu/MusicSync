import os.path
from pprint import pprint

import pandas as pd
import yt_dlp

from src.bookmark_library import BookmarkLibrary
from src.music_sync_library import Collection, CollectionUrl, MusicSyncLibrary, Track, TrackSyncStatus


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
                       'compat_opts': ['no-youtube-unavailable-videos']
                       }

    def __init__(self, params=None, auto_init=True):
        if params is None:
            params = {}
        params = self.DEFAULT_OPTIONS.copy() | params
        super(MusicSyncDownloader, self).__init__(params=params, auto_init=auto_init)

    def update_sync_status(self, collection: Collection) -> pd.DataFrame:
        # updating collection urls if sync with bookmarks is enabled
        if collection.sync_bookmark_file:
            bookmarks = BookmarkLibrary.create_from_path(collection.sync_bookmark_file)
            folder = bookmarks.go_to_path([e.id for e in collection.sync_bookmark_path]).get_all_bookmarks()
            for child in folder.values():
                if child.url not in collection.urls:
                    collection.urls.append(CollectionUrl(url=child.url,
                                                         name=child.bookmark_title if collection.sync_bookmark_title_as_url_name else ''))

        sync_status = pd.DataFrame(columns=['collection', 'url_name', 'file_path', 'track_title', 'status', 'action'])

        collection_base_dir = os.listdir(collection.folder_path)

        # download track info of all collection urls
        for url in collection.urls:
            info = self.extract_info(url.url, process=False)
            url.name = info['title']
            is_playlist = info.get('_type') == 'playlist'

            if is_playlist:
                entries = list(info['entries'])
                remote_urls = [(e['url'], e['title']) for e in entries]
                info['entries'] = entries
            else:
                remote_urls = [(info.get('original_url') or info.get('webpage_url'), info['title'])]

            if collection.save_playlists_to_subfolders and is_playlist:
                url_folder = os.path.join(collection.folder_path, url.name)
                url_folder_contents = os.listdir(url_folder) if os.path.isdir(url_folder) else []
            else:
                url_folder = collection.folder_path
                url_folder_contents = collection_base_dir

            for local_track in url.tracks.values():
                if local_track.url not in remote_urls:
                    if local_track.status == TrackSyncStatus.DOWNLOADED:
                        # 1. REMOVED_FROM_SOURCE: Track is not present in source, but was present in previous sync
                        local_track.status = TrackSyncStatus.REMOVED_FROM_SOURCE
                    elif local_track.status != TrackSyncStatus.PERMANENTLY_DOWNLOADED:
                        # 2. LOCAL_FILE: File is not in the permanently downloaded files, and does not correspond to a source track
                        local_track.status = TrackSyncStatus.LOCAL_FILE

            for remote_url, remote_title in remote_urls:
                # 3. ADDED_TO_SOURCE: Track is present in source, but was not present in previous sync
                if remote_url not in url.tracks:
                    url.tracks[remote_url] = Track(url=remote_url,
                                                   status=TrackSyncStatus.ADDED_TO_SOURCE,
                                                   title=remote_title,
                                                   path=url_folder,)
                else:
                    local_track: Track = url.tracks[remote_url]
                    if local_track.path not in url_folder_contents:
                        # 4. NOT_DOWNLOADED: Track is present in source, was also present in previous sync, but corresponding file does not exist
                        local_track.status = TrackSyncStatus.NOT_DOWNLOADED
                    elif local_track.status != TrackSyncStatus.PERMANENTLY_DOWNLOADED:
                        # 5. DOWNLOADED: Track is present in source and the corresponding file exists
                        local_track.status = TrackSyncStatus.DOWNLOADED
                    # (Implicit) 6. PERMANENTLY_DOWNLOADED: File is present in the permanently downloaded files


            df = pd.DataFrame(data={'collection': [collection.name] * len(url.tracks),
                                    'url_name': [url.name or url.url] * len(url.tracks),
                                    'file_path': [track.path for track in url.tracks.values()],
                                    'track_title': [track.title for track in url.tracks.values()],
                                    'status': [track.status for track in url.tracks.values()],
                                    'action': [collection.sync_actions[track.status] for track in url.tracks.values()]
                                    })
            sync_status = pd.concat([sync_status, df]).reset_index(drop=True)

        return sync_status

if __name__ == '__main__':
    library = MusicSyncLibrary.read_xml('../../a.xml')
    collection = library.children[0].children[0]
    downloader = MusicSyncDownloader()

    downloader.update_sync_status(collection)
