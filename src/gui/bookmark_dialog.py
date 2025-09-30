from PySide6.QtWidgets import QDialog, QTreeWidgetItem, QFileDialog, QDialogButtonBox

from src.bookmark_library import BookmarkLibrary, BookmarkFolder, Bookmark
from src.gui.bookmark_gui import Ui_Dialog


class BookmarkDialog(QDialog, Ui_Dialog):
    def __init__(self, parent=None):
        super(BookmarkDialog, self).__init__(parent)
        self.setupUi(self)

        self.bookmark_path_entry.textChanged.connect(self.load_file)
        self.browse_button.pressed.connect(self.browse_file)
        self.bookmark_tree_widget.expanded.connect(self.expanded)
        self.buttonBox.button(QDialogButtonBox.Ok).clicked.connect(self.close)

    def browse_file(self):
        filename, ok = QFileDialog.getOpenFileName(self, 'Select a file to load', filter='Firefox bookmark file (places.sqlite) (places.sqlite)')
        if filename:
            self.bookmark_path_entry.setText(filename)

    def load_file(self):
        def append_tree(parent: QTreeWidgetItem | None, children: dict):
            for child in children.values():
                if isinstance(child, BookmarkFolder):
                    new_child = QTreeWidgetItem([child.title, '', '', child.id])
                    append_tree(new_child, child.children)
                elif isinstance(child, Bookmark):
                    new_child = QTreeWidgetItem([child.bookmark_title, child.page_title, child.url, child.id])

                if parent is None:
                    self.bookmark_tree_widget.addTopLevelItem(new_child)
                else:
                    parent.addChild(new_child)

        path = self.bookmark_path_entry.text()
        library = BookmarkLibrary.create_from_path(path)
        append_tree(None, library.children)
        self.expanded()

    def expanded(self, *args):
        for i in range(self.bookmark_tree_widget.columnCount()):
            self.bookmark_tree_widget.resizeColumnToContents(i)
