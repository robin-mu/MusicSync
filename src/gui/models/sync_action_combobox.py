from PySide6.QtGui import QStandardItemModel, QStandardItem

from src.music_sync_library import TrackSyncStatus, TrackSyncAction


class SyncActionComboboxModel(QStandardItemModel):
    ACTION_OPTIONS = {
        TrackSyncStatus.ADDED_TO_SOURCE: [TrackSyncAction.DOWNLOAD, TrackSyncAction.DO_NOTHING, TrackSyncAction.DECIDE_INDIVIDUALLY],
        TrackSyncStatus.NOT_DOWNLOADED: [TrackSyncAction.DOWNLOAD, TrackSyncAction.DO_NOTHING, TrackSyncAction.DECIDE_INDIVIDUALLY],
        TrackSyncStatus.REMOVED_FROM_SOURCE: [TrackSyncAction.DELETE, TrackSyncAction.DO_NOTHING, TrackSyncAction.KEEP_PERMANENTLY, TrackSyncAction.DECIDE_INDIVIDUALLY],
        TrackSyncStatus.LOCAL_FILE: [TrackSyncAction.DELETE, TrackSyncAction.DO_NOTHING, TrackSyncAction.KEEP_PERMANENTLY, TrackSyncAction.DECIDE_INDIVIDUALLY],
        TrackSyncStatus.PERMANENTLY_DOWNLOADED: [TrackSyncAction.DO_NOTHING, TrackSyncAction.REMOVE_FROM_PERMANENTLY_DOWNLOADED, TrackSyncAction.DECIDE_INDIVIDUALLY],
        TrackSyncStatus.DOWNLOADED: [TrackSyncAction.DO_NOTHING, TrackSyncAction.DOWNLOAD, TrackSyncAction.DECIDE_INDIVIDUALLY],
    }

    def __init__(self, status: TrackSyncStatus):
        super().__init__()
        for action in self.ACTION_OPTIONS[status]:
            self.invisibleRootItem().appendRow(SyncActionComboboxItem(action))


class SyncActionComboboxItem(QStandardItem):
    def __init__(self, action: TrackSyncAction):
        super().__init__()
        self.action = action
        self.setText(action.gui_string)
        self.setStatusTip(action.gui_status_tip)