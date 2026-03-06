from PySide6.QtGui import QStandardItem, QStandardItemModel

from musicsync.music_sync_library import GuiStrEnum
from musicsync.music_sync_library import TrackSyncStatus


class ActionComboboxItemModel(QStandardItemModel):
    def __init__(self, status: TrackSyncStatus):
        super().__init__()
        for action in TrackSyncStatus.ACTION_OPTIONS[status]:
            self.invisibleRootItem().appendRow(GuiComboboxItem(action))


class GuiComboboxItem(QStandardItem):
    def __init__(self, action: GuiStrEnum):
        super().__init__()
        self.action = action
        self.setText(action.gui_string)
        self.setStatusTip(action.gui_status_tip)
