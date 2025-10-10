from PySide6.QtGui import QStandardItemModel, QStandardItem

from src.music_sync_library import TrackSyncStatus, TrackSyncAction


class SyncActionComboboxModel(QStandardItemModel):
    def __init__(self, status: TrackSyncStatus):
        super().__init__()
        for action in TrackSyncStatus.action_options()[status]:
            self.invisibleRootItem().appendRow(SyncActionComboboxItem(action))


class SyncActionComboboxItem(QStandardItem):
    def __init__(self, action: TrackSyncAction):
        super().__init__()
        self.action = action
        self.setText(action.gui_string)
        self.setStatusTip(action.gui_status_tip)