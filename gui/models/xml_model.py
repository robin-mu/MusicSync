from abc import abstractmethod, ABC, ABCMeta

from PySide6.QtCore import QAbstractItemModel, QModelIndex, Qt, QPersistentModelIndex
from PySide6.QtGui import QStandardItem, QStandardItemModel

from musicsync.xml_object import XmlObject

QStandardItemMeta = type(QStandardItem)


class _ABCQStandardItemMeta(QStandardItemMeta, ABCMeta):
    pass


QStandardItemModelMeta = type(QStandardItemModel)


class _ABCQStandardItemModelMeta(QStandardItemModelMeta, ABCMeta):
    pass


class XmlObjectModelItem(ABC):
    def __init__(self, xml_object: XmlObject | None = None, parent: XmlObjectModelItem | None = None, children: list[XmlObjectModelItem] | None = None):
        if children is None:
            children: list[XmlObjectModelItem] = []

        self.item_parent: XmlObjectModelItem | None = parent
        self.item_children: list[XmlObjectModelItem] = children

        self.xml_object = xml_object

    def child(self, row: int) -> XmlObjectModelItem | None:
        if row >= self.row_count() or row < 0:
            return None

        return self.item_children[row]

    def row_count(self) -> int:
        return len(self.item_children)

    def row(self) -> int:
        if self.item_parent is None:
            return 0
        return self.item_parent.item_children.index(self)

    def insert_child(self, row: int, child: XmlObjectModelItem):
        child.item_parent = self
        self.item_children.insert(row, child)

    def append_child(self, child: XmlObjectModelItem):
        self.insert_child(self.row_count(), child)

    def pop_child(self, row: int):
        child = self.item_children.pop(row)
        child.item_parent = None
        return child

    @abstractmethod
    def display_data(self) -> str:
        pass

    @abstractmethod
    def pull_from_xml_object(self):
        pass

    @abstractmethod
    def push_to_xml_object(self):
        pass


class RootItem(XmlObjectModelItem):
    def __init__(self, children: list[XmlObjectModelItem] | None = None):
        super().__init__(parent=None, children=children)

    def display_data(self) -> str:
        return ''

    def push_to_xml_object(self):
        pass

    def pull_from_xml_object(self):
        pass


class XmlObjectModel(QAbstractItemModel, ABC):
    """
    A QAbstractItemModel whose items are `XmlObjectModelItem`s.
    """

    def __init__(self, parent=None):
        super(XmlObjectModel, self).__init__(parent)
        self.root: XmlObjectModelItem = RootItem()

    def columnCount(self, /, parent: QModelIndex = QModelIndex()) -> int:
        return 1

    def rowCount(self, /, parent: QModelIndex = QModelIndex()) -> int:
        return self.get_item(parent).row_count()

    def index(self, row, column, parent: QModelIndex = QModelIndex()) -> QModelIndex:
        if not self.hasIndex(row, column, parent):
            return QModelIndex()

        parent_item = self.get_item(parent)
        child_item = parent_item.child(row)
        if not child_item:
            return QModelIndex()

        return self.createIndex(row, column, child_item)

    def parent(self, index: QModelIndex) -> QModelIndex:
        if not index.isValid():
            return QModelIndex()

        item = self.get_item(index)
        parent_item = item.item_parent

        if parent_item is None or parent_item is self.root:
            return QModelIndex()

        assert parent_item is not None
        return self.createIndex(parent_item.row(), 0, parent_item)

    def data(self, index, role=Qt.ItemDataRole.DisplayRole):
        if not index.isValid():
            return None

        item = self.get_item(index)
        if role == Qt.ItemDataRole.DisplayRole:
            return item.display_data()

        return None

    def flags(self, index: QModelIndex):
        flags = Qt.ItemFlag.ItemIsSelectable | Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsEditable | Qt.ItemFlag.ItemIsDropEnabled
        if index.isValid() and self.item_is_container(self.get_item(index)):
            flags |= Qt.ItemFlag.ItemIsDropEnabled

        return flags

    def get_item(self, index: QModelIndex | QPersistentModelIndex) -> XmlObjectModelItem:
        if index.isValid():
            return index.internalPointer()
        return self.root

    def supportedDropActions(self, /):
        return Qt.DropAction.MoveAction

    def moveRows(self, source_parent: QModelIndex, source_row: int, count: int, destination_parent: QModelIndex,
                 destination_child: int, /):
        if count != 1:
            return False

        source_parent_item = self.get_item(source_parent)
        destination_parent_item = self.get_item(destination_parent)

        # Disallow moving into itself or its descendants
        item = source_parent_item.child(source_row)
        p = destination_parent_item
        while p is not None:
            if p is item:
                return False
            p = p.item_parent

        if source_parent != destination_parent and destination_child > source_row:
            destination_child -= 1

        if not self.validate_move(source_parent, source_row, destination_parent, destination_child):
            return False

        self.beginMoveRows(source_parent, source_row, source_row, destination_parent, destination_child)
        moved_item = source_parent_item.pop_child(source_row)
        destination_parent_item.insert_child(destination_child, moved_item)
        self.endMoveRows()

        return True

    @abstractmethod
    def validate_move(self, source_parent: QModelIndex, source_row: int, destination_parent: QModelIndex, destination_child: int) -> bool:
        pass

    @abstractmethod
    def item_is_container(self, item: XmlObjectModelItem) -> bool:
        pass

    @abstractmethod
    def push_to_xml_object(self):
        pass

    @abstractmethod
    def pull_from_xml_object(self):
        pass