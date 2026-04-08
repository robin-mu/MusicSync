from abc import abstractmethod, ABC, ABCMeta

from PySide6.QtCore import QAbstractItemModel, QModelIndex, Qt, QPersistentModelIndex
from PySide6.QtGui import QIcon, QFont

from musicsync.xml_object import XmlObject

QAbstractItemModelMeta = type(QAbstractItemModel)


class _ABCQAbstractItemModelMeta(QAbstractItemModelMeta, ABCMeta):
    pass


class XmlObjectModelItem(ABC):
    def __init__(self, xml_object: XmlObject | None, icon: QIcon = QIcon(), font: QFont = QFont()):
        self.parent: XmlObjectModelItem | None = None
        self.children: list[XmlObjectModelItem] = []

        self.xml_object = xml_object

        self.model: XmlObjectModel | None = None

        self.icon = icon
        self.font = font

    def child(self, row: int) -> XmlObjectModelItem:
        return self.children[row]

    def row_count(self) -> int:
        return len(self.children)

    def row(self) -> int:
        if self.parent is None:
            return 0
        return self.parent.children.index(self)

    def _insert_child(self, row: int, child: XmlObjectModelItem):
        child.parent = self
        self.children.insert(row, child)

    def _append_child(self, child: XmlObjectModelItem):
        self._insert_child(self.row_count(), child)

    def _pop_child(self, row: int):
        child = self.children.pop(row)
        child.parent = None
        return child

    def append_row(self, item: XmlObjectModelItem):
        assert self.model is not None

        self.model.insert_item_at_item(item, self.row_count(), self)

    def remove_rows(self, row: int, count: int):
        assert self.model is not None

        self.model.remove_rows_from_item(row, count, self)

    @abstractmethod
    def get_text(self) -> str:
        pass

    @abstractmethod
    def set_text(self, value: str):
        pass

    @abstractmethod
    def pull_from_xml_object(self):
        pass

    @abstractmethod
    def push_to_xml_object(self):
        pass


class RootItem(XmlObjectModelItem):
    def __init__(self):
        super().__init__(xml_object=None)

    def get_text(self) -> str:
        return ''

    def set_text(self, value: str):
        pass

    def push_to_xml_object(self):
        pass

    def pull_from_xml_object(self):
        pass


class XmlObjectModel(QAbstractItemModel, ABC, metaclass=_ABCQAbstractItemModelMeta):
    """
    A QAbstractItemModel whose items are `XmlObjectModelItem`s.
    """

    def __init__(self, parent=None):
        super(XmlObjectModel, self).__init__(parent)
        self.root: XmlObjectModelItem = RootItem()

    def columnCount(self, /, parent: QModelIndex = QModelIndex()) -> int:
        return 1

    def rowCount(self, /, parent: QModelIndex = QModelIndex()) -> int:
        return self.item_from_index(parent).row_count()

    def index(self, row, column, parent: QModelIndex = QModelIndex()) -> QModelIndex:
        if not self.hasIndex(row, column, parent):
            return QModelIndex()

        parent_item = self.item_from_index(parent)
        child_item = parent_item.child(row)
        if not child_item:
            return QModelIndex()

        return self.createIndex(row, column, child_item)

    def parent(self, index: QModelIndex) -> QModelIndex:
        if not index.isValid():
            return QModelIndex()

        item = self.item_from_index(index)
        parent_item = item.parent

        if parent_item is None or parent_item is self.root:
            return QModelIndex()

        assert parent_item is not None
        return self.createIndex(parent_item.row(), 0, parent_item)

    def data(self, index, role=Qt.ItemDataRole.DisplayRole):
        if not index.isValid():
            return None

        item = self.item_from_index(index)
        if role == Qt.ItemDataRole.DisplayRole:
            return item.get_text()

        if role == Qt.ItemDataRole.DecorationRole:
            return item.icon

        if role == Qt.ItemDataRole.FontRole:
            return item.font

        return None

    def setData(self, index, value, /, role: Qt.ItemDataRole = Qt.ItemDataRole.EditRole) -> bool:
        if not index.isValid():
            return False

        if role == Qt.ItemDataRole.EditRole:
            item = self.item_from_index(index)
            item.set_text(str(value))
            self.dataChanged.emit(index, index, [role])
            return True

        return False

    def flags(self, index: QModelIndex):
        if not index.isValid():
            return Qt.ItemFlag.NoItemFlags

        flags = Qt.ItemFlag.ItemIsSelectable | Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsDropEnabled | Qt.ItemFlag.ItemIsEditable

        if self.item_is_container(self.item_from_index(index)):
            flags |= Qt.ItemFlag.ItemIsDropEnabled

        return flags

    def item_from_index(self, index: QModelIndex | QPersistentModelIndex) -> XmlObjectModelItem:
        if index.isValid():
            return index.internalPointer()
        return self.root

    def index_from_item(self, item: XmlObjectModelItem | None):
        if item is None or item is self.root:
            return QModelIndex()

        return self.createIndex(item.row(), 0, item)

    def supportedDropActions(self, /):
        return Qt.DropAction.MoveAction

    def moveRows(self, source_parent: QModelIndex, source_row: int, count: int, destination_parent: QModelIndex,
                 destination_child: int, /):
        if count != 1:
            return False

        source_parent_item = self.item_from_index(source_parent)
        destination_parent_item = self.item_from_index(destination_parent)

        # Disallow moving into itself or its descendants
        item = source_parent_item.child(source_row)
        p = destination_parent_item
        while p is not None:
            if p is item:
                return False
            p = p.parent

        if source_parent != destination_parent and destination_child > source_row:
            destination_child -= 1

        if not self.validate_move(source_parent, source_row, destination_parent, destination_child):
            return False

        self.beginMoveRows(source_parent, source_row, source_row, destination_parent, destination_child)
        moved_item = source_parent_item._pop_child(source_row)
        destination_parent_item._insert_child(destination_child, moved_item)
        self.endMoveRows()

        return True

    def insertRows(self, row: int, count: int, /, parent: QModelIndex = QModelIndex()) -> bool:
        # let's hope it works without implementing this
        pass

    def insert_item_at_index(self, item: XmlObjectModelItem, row: int | None = None, parent: QModelIndex = QModelIndex()):
        parent_item = self.item_from_index(parent)
        if row is None:
            row: int = parent_item.row_count()

        item.model = self

        self.beginInsertRows(parent, row, row)
        parent_item._insert_child(row, item)
        self.endInsertRows()

    def insert_item_at_item(self, item: XmlObjectModelItem, row: int | None = None, parent: XmlObjectModelItem | None = None):
        self.insert_item_at_index(item, row, self.index_from_item(parent))

    def removeRows(self, row: int, count: int, /, parent: QModelIndex = QModelIndex()) -> bool:
        parent_item = self.item_from_index(parent)

        if count <= 0:
            return False

        if row < 0 or row + count > parent_item.row_count():
            return False

        self.beginRemoveRows(parent, row, row + count - 1)
        for child in parent_item.children[row:row + count]:
            child.parent = None
            child.model = None
        del parent_item.children[row:row + count]
        self.endRemoveRows()

        return True

    def remove_rows_from_item(self, row: int, count: int, parent: XmlObjectModelItem | None = None) -> bool:
        return self.removeRows(row, count, self.index_from_item(parent))

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