from PySide6 import QtWidgets

from src.gui.metadata_suggestions_gui import Ui_Dialog
from src.gui.models.metadata_fields_model import MetadataFieldsModel, CheckboxDelegate
from src.music_sync_library import MetadataField


class MetadataSuggestionsDialog(QtWidgets.QDialog, Ui_Dialog):
    def __init__(self, metadata_suggestions: list[MetadataField], parent=None):
        super(MetadataSuggestionsDialog, self).__init__(parent)
        self.setupUi(self)

        self.columns_table.setModel(MetadataFieldsModel(metadata_suggestions, parent=self))
        for col in range(1, 4):
            self.columns_table.setItemDelegateForColumn(col, CheckboxDelegate(self))

            for row in range(self.columns_table.model().rowCount()):
                self.columns_table.openPersistentEditor(self.columns_table.model().index(row, col))

        self.columns_table.resizeColumnsToContents()