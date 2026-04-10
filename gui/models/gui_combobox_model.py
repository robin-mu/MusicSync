from PySide6.QtGui import QStandardItem, QStandardItemModel

from musicsync.music_sync_library import GuiStrEnum
from musicsync.music_sync_library import TrackSyncStatus
from musicsync.scripting.script_types import DownloadScriptWhen


class GuiComboboxItem(QStandardItem):
    def __init__(self, member: GuiStrEnum):
        super().__init__()
        self.member = member
        self.setText(member.gui_string)
        self.setStatusTip(member.gui_status_tip)


class ActionComboboxItemModel(QStandardItemModel):
    def __init__(self, status: TrackSyncStatus):
        super().__init__()
        for action in TrackSyncStatus.ACTION_OPTIONS[status]:
            self.invisibleRootItem().appendRow(GuiComboboxItem(action))


class DownloadScriptComboboxItemModel(QStandardItemModel):
    def __init__(self):
        super().__init__()
        for when in DownloadScriptWhen.__members__.values():
            self.invisibleRootItem().appendRow(GuiComboboxItem(when))