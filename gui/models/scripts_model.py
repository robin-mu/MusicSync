from enum import IntEnum
from typing import cast

from PySide6 import QtCore, QtWidgets
from PySide6.QtCore import Qt, QModelIndex
from PySide6.QtGui import QStandardItem, QStandardItemModel
from PySide6.QtWidgets import QCheckBox

from musicsync.music_sync_library import Script
from musicsync.scripting.script_types import ScriptType

class ScriptTypeItem(QStandardItem):
    def __init__(self, script_type: ScriptType):
        super(ScriptTypeItem, self).__init__(script_type.gui_string)
        self.setEditable(False)
        self.setSelectable(True)
        self.setCheckable(False)

        self.cls = script_type.cls

class ScriptItem(QStandardItem):
    def __init__(self, script: Script):
        super().__init__(script.name)
        self.setEditable(True)
        self.setSelectable(True)
        self.setCheckable(True)
        self.setCheckState(Qt.CheckState.Checked if script.enabled else Qt.CheckState.Unchecked)

        self.script = script


class ScriptsModel(QStandardItemModel):
    def __init__(self, scripts: list[Script]=None, window=None):
        super(ScriptsModel, self).__init__()

        self.window = window

        self.script_types: dict[ScriptType, ScriptTypeItem] = {}
        for typ in ScriptType.__members__.values():
            item = ScriptTypeItem(typ)

            self.script_types[typ] = item
            self.appendRow(item)

        for script in scripts:
            self.script_types[script.script_type].appendRow(ScriptItem(script))

    def update_checkboxes(self, enabled_scripts: list[str]):
        for it in self.items:
            it.setCheckState(Qt.CheckState.Checked if it.script.name in enabled_scripts else Qt.CheckState.Unchecked)

    def add_script(self, index: QModelIndex):
        child = self.itemFromIndex(index)
        if isinstance(child, ScriptItem):
            parent = child.parent()
            new_row = child.row() + 1
        else:
            parent = child
            new_row = parent.rowCount()
        parent = cast(ScriptTypeItem, parent)

        script = parent.cls('')
        item = ScriptItem(script)

        parent.insertRow(new_row, [item])

        return self.indexFromItem(item)

    def remove_script(self, index: QModelIndex):
        item = self.itemFromIndex(index)
        if isinstance(item, ScriptTypeItem):
            return

        parent = cast(ScriptTypeItem, item.parent())

        parent.removeRow(item.row())

    @property
    def scripts(self) -> list[Script]:
        return [it.script for it in self.items]

    @property
    def items(self) -> list[ScriptItem]:
        items: list[ScriptItem] = []
        for script_type_item in self.script_types.values():
            for i in range(script_type_item.rowCount()):
                items.append(cast(ScriptItem, script_type_item.child(i)))

        return items