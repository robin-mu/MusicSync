from PySide6 import QtCore, QtWidgets
from PySide6.QtCore import QEvent, QItemSelection, QModelIndex, QUrl
from PySide6.QtGui import QCursor, QDesktopServices
from PySide6.QtWidgets import QApplication, QStyle

from src.gui.metadata_suggestions_gui import Ui_Dialog
from src.gui.models.external_metadata_tables_model import ExternalMetadataTablesColumn, ExternalMetadataTablesModel
from src.gui.models.file_tags_model import FileTagsModel, FileTagsTableColumn
from src.gui.models.metadata_fields_model import CheckboxDelegate, MetadataFieldsModel, MetadataFieldsTableColumn
from src.gui.models.metadata_suggestions_model import MetadataSuggestionsModel, MetadataSuggestionsTableColumn
from src.music_sync_library import ExternalMetadataTable, FileTag, MetadataField, MetadataSuggestion


class MetadataSuggestionsDialog(QtWidgets.QDialog, Ui_Dialog):
    def __init__(self, metadata_suggestions: list[MetadataField], external_metadata_tables: list[ExternalMetadataTable],
                 file_tags: list[FileTag], parent=None):
        super(MetadataSuggestionsDialog, self).__init__(parent)
        self.setupUi(self)

        self.buttonBox.accepted.connect(self.accept)
        self.buttonBox.rejected.connect(self.reject)

        # Metadata fields table
        self.fields_table.setModel(MetadataFieldsModel(metadata_suggestions, parent=self))
        for col in [MetadataFieldsTableColumn.ENABLED, MetadataFieldsTableColumn.TIMED_DATA, MetadataFieldsTableColumn.SHOW_FORMAT_OPTIONS, MetadataFieldsTableColumn.DEFAULT_FORMAT_AS_TITLE, MetadataFieldsTableColumn.DEFAULT_REMOVE_BRACKETS]:
            self.fields_table.setItemDelegateForColumn(col, CheckboxDelegate(self))

            for row in range(self.fields_table.model().rowCount()):
                self.fields_table.openPersistentEditor(self.fields_table.model().index(row, col))

        self.fields_table.sortByColumn(MetadataFieldsTableColumn.ENABLED, QtCore.Qt.SortOrder.AscendingOrder)
        self.fields_table.resizeColumnsToContents()

        self.fields_table.selectionModel().selectionChanged.connect(self.field_selection_changed)

        self.field_add_button.pressed.connect(self.add_field)
        self.field_remove_button.pressed.connect(self.remove_field)

        self.suggestions_table.setStyle(MetadataSuggestionsTableStyle())
        self.suggestions_table.horizontalHeader().setMouseTracking(True)
        self.suggestions_table.horizontalHeader().sectionClicked.connect(self.suggestions_table_header_clicked)
        self.suggestions_table.horizontalHeader().installEventFilter(self)
        self.installEventFilter(self)

        self.suggestions_add_button.pressed.connect(self.add_suggestion)
        self.suggestions_remove_button.pressed.connect(self.remove_suggestion)

        self.external_tables_table.setModel(ExternalMetadataTablesModel(external_metadata_tables, parent=self))
        self.external_tables_table.resizeColumnsToContents()

        self.external_table_add_button.pressed.connect(self.add_external_table)
        self.external_table_remove_button.pressed.connect(self.remove_external_table)

        self.tags_table.setModel(FileTagsModel(file_tags, parent=self))
        self.tags_table.resizeColumnsToContents()

        self.tag_add_button.pressed.connect(self.add_tag)
        self.tag_remove_button.pressed.connect(self.remove_tag)

    def add_field(self):
        self.fields_table.model().beginInsertRows(QModelIndex(), self.fields_table.model().rowCount(), self.fields_table.model().rowCount())
        self.fields_table.model().fields.append(MetadataField('', []))

        for col in [MetadataFieldsTableColumn.ENABLED, MetadataFieldsTableColumn.SHOW_FORMAT_OPTIONS,
                MetadataFieldsTableColumn.DEFAULT_FORMAT_AS_TITLE, MetadataFieldsTableColumn.DEFAULT_REMOVE_BRACKETS]:
            self.fields_table.openPersistentEditor(self.fields_table.model().index(self.fields_table.model().rowCount() - 1, col))
        self.fields_table.model().endInsertRows()

        new_index = self.fields_table.model().index(self.fields_table.model().rowCount() - 1, MetadataFieldsTableColumn.NAME)
        self.fields_table.edit(new_index)

    def remove_field(self):
        index = self.fields_table.currentIndex().row()
        if index == -1:
            return
        self.fields_table.model().beginRemoveRows(QModelIndex(), index, index)
        self.fields_table.model().fields.pop(index)
        self.fields_table.model().endRemoveRows()

    def field_selection_changed(self, selected: QItemSelection, deselected: QItemSelection):
        if selected.isEmpty():
            return
        field = self.fields_table.model().fields[selected.indexes()[0].row()]
        self.selected_field_label.setText(self.selected_field_label.text().split(':')[0] + ': ' + field.name)
        self.suggestions_table.setModel(MetadataSuggestionsModel(field.suggestions, parent=self))
        self.suggestions_table.resizeColumnsToContents()

    def eventFilter(self, obj, event):
        def over_resize_handle(pos):
            idx = self.suggestions_table.horizontalHeader().logicalIndexAt(pos)
            if idx < 0:
                return False
            left = self.suggestions_table.horizontalHeader().sectionPosition(idx)
            right = left + self.suggestions_table.horizontalHeader().sectionSize(idx)
            margin = 3
            return abs(pos.x() - left) <= margin or abs(pos.x() - right) <= margin

        def update_cursor():
            global_pos = QCursor.pos()
            pos = self.suggestions_table.horizontalHeader().mapFromGlobal(global_pos)
            over_idx = self.suggestions_table.horizontalHeader().logicalIndexAt(pos)
            if over_idx == -1:
                return

            idx_url = MetadataSuggestionsTableColumn(over_idx).doc_url()

            if et == QEvent.Type.KeyPress and event.key() == QtCore.Qt.Key.Key_Control:
                ctrl_down = True
            elif et == QEvent.Type.KeyRelease and event.key() == QtCore.Qt.Key.Key_Control:
                ctrl_down = False
            else:
                ctrl_down = QApplication.keyboardModifiers() == QtCore.Qt.KeyboardModifier.ControlModifier

            if over_resize_handle(pos):
                self.suggestions_table.horizontalHeader().setCursor(QCursor(QtCore.Qt.CursorShape.SplitHCursor))
                return

            if idx_url and ctrl_down:
                self.suggestions_table.horizontalHeader().setCursor(QtCore.Qt.CursorShape.PointingHandCursor)
            else:
                self.suggestions_table.horizontalHeader().unsetCursor()

        et = event.type()

        header_events = (QEvent.Type.Enter, QEvent.Type.HoverEnter, QEvent.Type.Leave, QEvent.Type.HoverLeave,
                         QEvent.Type.MouseMove, QEvent.Type.HoverMove)

        if obj is self.suggestions_table.horizontalHeader() and et in header_events or obj is self and et in (QEvent.Type.KeyPress, QEvent.Type.KeyRelease):
            update_cursor()

        return False

    def suggestions_table_header_clicked(self, section: int):
        modifier = QtWidgets.QApplication.keyboardModifiers()
        sec_url = MetadataSuggestionsTableColumn(section).doc_url()
        if modifier == QtCore.Qt.KeyboardModifier.ControlModifier:
            QDesktopServices.openUrl(QUrl(sec_url))

    def add_suggestion(self):
        if self.suggestions_table.model() is None:
            return

        row_idx = self.suggestions_table.currentIndex().row()
        if row_idx != -1 and QApplication.keyboardModifiers() == QtCore.Qt.KeyboardModifier.ShiftModifier:
            new_idx = row_idx + 1
        else:
            new_idx = self.suggestions_table.model().rowCount()

        self.suggestions_table.model().beginInsertRows(QModelIndex(), new_idx, new_idx)
        self.suggestions_table.model().suggestions.insert(new_idx, MetadataSuggestion(''))
        self.suggestions_table.model().endInsertRows()

        new_index = self.suggestions_table.model().index(new_idx, MetadataSuggestionsTableColumn.FROM)
        self.suggestions_table.edit(new_index)

    def remove_suggestion(self):
        if self.suggestions_table.model() is None or self.suggestions_table.currentIndex().row() == -1:
            return

        remove_idx = self.suggestions_table.currentIndex().row()
        self.suggestions_table.model().beginRemoveRows(QModelIndex(), remove_idx, remove_idx)
        self.suggestions_table.model().suggestions.pop(remove_idx)
        self.suggestions_table.model().endRemoveRows()

    def add_external_table(self):
        self.external_tables_table.model().beginInsertRows(QModelIndex(), self.external_tables_table.model().rowCount(), self.external_tables_table.model().rowCount())

        new_id = max(self.external_tables_table.model().tables, key=lambda t: t.id).id + 1
        self.external_tables_table.model().tables.append(ExternalMetadataTable(new_id))

        self.external_tables_table.model().endInsertRows()

        new_index = self.external_tables_table.model().index(self.external_tables_table.model().rowCount() - 1, ExternalMetadataTablesColumn.NAME)
        self.external_tables_table.edit(new_index)

    def remove_external_table(self):
        index = self.external_tables_table.currentIndex().row()
        if index <= 0:
            return

        self.external_tables_table.model().beginRemoveRows(QModelIndex(), index, index)
        self.external_tables_table.model().tables.pop(index)
        self.external_tables_table.model().endRemoveRows()

    def add_tag(self):
        self.tags_table.model().beginInsertRows(QModelIndex(), self.tags_table.model().rowCount(), self.tags_table.model().rowCount())
        self.tags_table.model().tags.append(FileTag(self.tag_combobox.currentText()))
        self.tags_table.model().endInsertRows()

        new_index = self.tags_table.model().index(self.tags_table.model().rowCount() - 1, FileTagsTableColumn.FORMAT)
        self.tags_table.edit(new_index)

    def remove_tag(self):
        index = self.tags_table.currentIndex().row()
        if index == -1:
            return

        self.tags_table.model().beginRemoveRows(QModelIndex(), index, index)
        self.tags_table.model().tags.pop(index)
        self.tags_table.model().endRemoveRows()


class MetadataSuggestionsTableStyle(QtWidgets.QProxyStyle):
    def drawPrimitive(self, element, option, painter, widget=None):
        if element == QStyle.PrimitiveElement.PE_IndicatorItemViewItemDrop and not option.rect.isNull():
            option.rect.setHeight(1)
        super().drawPrimitive(element, option, painter, widget)
