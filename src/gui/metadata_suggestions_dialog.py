from PySide6 import QtWidgets, QtCore
from PySide6.QtCore import QItemSelection
from PySide6.QtGui import QDropEvent
from PySide6.QtWidgets import QStyle, QTableView

from src.gui.metadata_suggestions_gui import Ui_Dialog
from src.gui.models.metadata_fields_model import MetadataFieldsModel, CheckboxDelegate, MetadataFieldsTableColumn
from src.gui.models.metadata_suggestions_model import MetadataSuggestionsModel
from src.music_sync_library import MetadataField


class MetadataSuggestionsDialog(QtWidgets.QDialog, Ui_Dialog):
    def __init__(self, metadata_suggestions: list[MetadataField], parent=None):
        super(MetadataSuggestionsDialog, self).__init__(parent)
        self.setupUi(self)

        # Metadata fields table
        self.fields_table.setModel(MetadataFieldsModel(metadata_suggestions, parent=self))
        for col in [MetadataFieldsTableColumn.ENABLED, MetadataFieldsTableColumn.SHOW_FORMAT_OPTIONS, MetadataFieldsTableColumn.DEFAULT_FORMAT_AS_TITLE, MetadataFieldsTableColumn.DEFAULT_REMOVE_BRACKETS]:
            self.fields_table.setItemDelegateForColumn(col, CheckboxDelegate(self))

            for row in range(self.fields_table.model().rowCount()):
                self.fields_table.openPersistentEditor(self.fields_table.model().index(row, col))

        self.fields_table.sortByColumn(MetadataFieldsTableColumn.ENABLED, QtCore.Qt.SortOrder.AscendingOrder)
        self.fields_table.resizeColumnsToContents()

        self.fields_table.selectionModel().selectionChanged.connect(self.field_selection_changed)

        self.field_add_button.pressed.connect(self.add_field)
        self.field_remove_button.pressed.connect(self.remove_field)

        self.suggestions_table.setStyle(MetadataSuggestionsTableStyle())

    def add_field(self):
        self.fields_table.model().layoutAboutToBeChanged.emit()
        self.fields_table.model().fields.append(MetadataField('', []))

        for col in [MetadataFieldsTableColumn.ENABLED, MetadataFieldsTableColumn.SHOW_FORMAT_OPTIONS,
                MetadataFieldsTableColumn.DEFAULT_FORMAT_AS_TITLE, MetadataFieldsTableColumn.DEFAULT_REMOVE_BRACKETS]:
            self.fields_table.openPersistentEditor(self.fields_table.model().index(self.fields_table.model().rowCount() - 1, col))
        self.fields_table.model().layoutChanged.emit()

        new_index = self.fields_table.model().index(self.fields_table.model().rowCount() - 1, MetadataFieldsTableColumn.NAME)
        self.fields_table.edit(new_index)

    def remove_field(self):
        self.fields_table.model().layoutAboutToBeChanged.emit()
        index = self.fields_table.currentIndex().row()
        self.fields_table.model().fields.pop(index)
        self.fields_table.model().layoutChanged.emit()

    def field_selection_changed(self, selected: QItemSelection, deselected: QItemSelection):
        field = self.fields_table.model().fields[selected.indexes()[0].row()]
        self.selected_field_label.setText(self.selected_field_label.text().split(':')[0] + ': ' + field.name)
        self.suggestions_table.setModel(MetadataSuggestionsModel(field.suggestions, parent=self))
        self.suggestions_table.resizeColumnsToContents()

class MetadataSuggestionsTableStyle(QtWidgets.QProxyStyle):
    def drawPrimitive(self, element, option, painter, widget=None):
        if element == QStyle.PrimitiveElement.PE_IndicatorItemViewItemDrop and not option.rect.isNull():
            option.rect.setHeight(1)
        super().drawPrimitive(element, option, painter, widget)