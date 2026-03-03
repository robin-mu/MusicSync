from typing import Any

from PySide6 import QtCore, QtWidgets
from PySide6.QtCore import QEvent, Qt, QTimer, QObject
from PySide6.QtWidgets import QComboBox


class ComboBoxDelegate(QtWidgets.QStyledItemDelegate):
    def __init__(self, editable: bool=False, update_callback=None, window=None, view=None):
        super(ComboBoxDelegate, self).__init__(window)
        self._editors = {}
        self.editable = editable
        self.update_callback = update_callback
        self.window = window
        self.view = view

        self.installEventFilter(self)

    def to_model_data(self, val: str) -> Any:
        return val

    def get_combobox_items(self, index) -> list[str]:
        return [index.model().data(index, role=QtCore.Qt.ItemDataRole.BackgroundRole)]

    def get_combobox_selection(self, index) -> str:
        return index.model().data(index, role=QtCore.Qt.ItemDataRole.BackgroundRole)

    def get_status_bar_text(self, index, box: QComboBox) -> str:
        return str(index)

    def paint(self, painter, option, index, /):
        opt = QtWidgets.QStyleOptionComboBox()
        opt.rect = option.rect
        opt.state = option.state
        opt.fontMetrics = option.fontMetrics

        text = index.model().data(index, role=QtCore.Qt.ItemDataRole.DisplayRole)
        opt.currentText = "" if text is None else str(text)
        opt.editable = self.editable
        opt.frame = True

        style = option.widget.style() if option.widget else QtWidgets.QApplication.style()
        style.drawComplexControl(QtWidgets.QStyle.ComplexControl.CC_ComboBox, opt, painter)
        style.drawControl(QtWidgets.QStyle.ControlElement.CE_ComboBoxLabel, opt, painter)

    def sizeHint(self, option, index, /):
        fm = option.fontMetrics

        items = self.get_combobox_items(index) + [self.get_combobox_selection(index)]
        max_text_w = max(fm.horizontalAdvance(i) for i in items)

        opt = QtWidgets.QStyleOptionComboBox()
        opt.rect = option.rect
        opt.fontMetrics = fm
        opt.currentText = 'X'
        opt.editable = self.editable
        opt.frame = True

        style = option.widget.style() if option.widget else QtWidgets.QApplication.style()

        content = QtCore.QSize(max_text_w, fm.height())
        total = style.sizeFromContents(QtWidgets.QStyle.ContentsType.CT_ComboBox, opt, content, option.widget)

        total.setWidth(total.width() + 6)
        return total

    def editorEvent(self, event, model, option, index, /):
        if event.type() == QEvent.Type.MouseButtonPress and event.button() == Qt.MouseButton.LeftButton:
            self.view.edit(index)
            return True

            # sm = self.view.selectionModel()
            # if sm is not None and (sm.isSelected(index) or sm.currentIndex() == index):
            #     self.view.edit(index)
            #     return True

        return super().editorEvent(event, model, option, index)

    def createEditor(self, parent, option, index):
        combo = QtWidgets.QComboBox(parent)
        combo.setEditable(self.editable)

        pindex = QtCore.QPersistentModelIndex(index)
        self._editors[pindex] = combo
        combo.destroyed.connect(lambda obj, pidx=pindex: self._editors.pop(pidx, None))
        combo.highlighted[int].connect(lambda index, box=combo: self.window.statusbar.showMessage(self.get_status_bar_text(index, box)))
        combo.activated.connect(lambda *_: self.commit_and_close(combo))
        combo.view().window().installEventFilter(_PopupCloseFilter(combo, self))
        QTimer.singleShot(0, combo.showPopup)
        return combo

    def commit_and_close(self, editor):
        if editor.property('_closing'):
            return
        editor.setProperty('_closing', True)
        self.commitData.emit(editor)
        self.closeEditor.emit(editor, QtWidgets.QAbstractItemDelegate.EndEditHint.NoHint)
        if self.update_callback is not None:
            self.update_callback(editor.currentText())

    def setEditorData(self, editor: QComboBox, index):
        editor.blockSignals(True)
        editor.clear()
        editor.addItems(self.get_combobox_items(index))
        editor.setCurrentText(self.get_combobox_selection(index))
        editor.blockSignals(False)

    def setModelData(self, editor: QComboBox, model, index):
        model.setData(index, self.to_model_data(editor.currentText()))

    def updateEditorGeometry(self, editor, option, index, /):
        editor.setGeometry(option.rect)

    def eventFilter(self, obj, event):
        if obj is self:
            if event.type() in (QEvent.Type.HoverMove, QEvent.Type.HoverEnter, QEvent.Type.MouseButtonPress):
                self.window.statusbar.showMessage(self.get_status_bar_text(obj.currentIndex(), obj))
            if event.type() in (QEvent.Type.Hide, QEvent.Type.FocusIn, QEvent.Type.HoverLeave):
                self.window.statusbar.clearMessage()

        return super(ComboBoxDelegate, self).eventFilter(obj, event)

class _PopupCloseFilter(QObject):
    def __init__(self, combo, delegate):
        super().__init__(combo)
        self.combo = combo
        self.delegate: ComboBoxDelegate = delegate

    def eventFilter(self, obj, event):
        if event.type() == QEvent.Type.Hide:
            QTimer.singleShot(0, lambda c=self.combo: self.delegate.commit_and_close(c))
        return False