from abc import abstractmethod, ABC, ABCMeta

from PySide6.QtCore import QAbstractItemModel, QModelIndex, Qt, QPersistentModelIndex, QMimeData, QDataStream, \
    QByteArray, QIODevice
from PySide6.QtGui import QIcon, QFont

from musicsync.xml_object import XmlObject

QAbstractItemModelMeta = type(QAbstractItemModel)


class _ABCQAbstractItemModelMeta(QAbstractItemModelMeta, ABCMeta):
    pass


class XmlObjectModelItem(ABC):
    def __init__(self, xml_object: XmlObject | None, icon: QIcon = None, font: QFont = None):
        if icon is None:
            icon = QIcon()

        if font is None:
            font = QFont()

        self.item_parent: XmlObjectModelItem | None = None
        self.item_children: list[XmlObjectModelItem] = []

        self.xml_object = xml_object

        self.model: XmlObjectModel | None = None

        self.icon = icon
        self.font = font

    @property
    def parent(self) -> XmlObjectModelItem | None:
        return self.item_parent

    def child(self, row: int) -> XmlObjectModelItem:
        return self.item_children[row]

    def row_count(self) -> int:
        return len(self.item_children)

    def row(self) -> int:
        if self.item_parent is None:
            return 0
        return self.item_parent.item_children.index(self)

    def _insert_child(self, row: int, child: XmlObjectModelItem):
        child.item_parent = self
        self.item_children.insert(row, child)

    def _append_child(self, child: XmlObjectModelItem):
        self._insert_child(self.row_count(), child)

    def _pop_child(self, row: int):
        child = self.item_children.pop(row)
        child.item_parent = None
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

        self._ignore_remove = False

    def columnCount(self, /, parent: QModelIndex = QModelIndex()) -> int:
        return 1

    def rowCount(self, /, parent: QModelIndex | QPersistentModelIndex = QModelIndex()) -> int:
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
        parent_item = item.item_parent

        if parent_item is None or parent_item is self.root:
            return QModelIndex()

        assert parent_item is not None
        return self.createIndex(parent_item.row(), 0, parent_item)

    def data(self, index, role=Qt.ItemDataRole.DisplayRole):
        if not index.isValid():
            return None

        item = self.item_from_index(index)
        if role in (Qt.ItemDataRole.DisplayRole, Qt.ItemDataRole.EditRole):
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

        flags = Qt.ItemFlag.ItemIsSelectable | Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsDragEnabled | Qt.ItemFlag.ItemIsEditable

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

        assert item is not None
        return self.createIndex(item.row(), 0, item)

    def supportedDropActions(self, /):
        return Qt.DropAction.MoveAction

    def mimeTypes(self, /):
        return ['application/x-xml-object-model-item']

    @staticmethod
    def path_from_index(index: QModelIndex) -> list[int]:
        path = []
        while index.isValid():
            path.insert(0, index.row())
            index = index.parent()
        return path

    def index_from_path(self, path: list[int]) -> QModelIndex:
        parent = QModelIndex()
        for row in path:
            parent = self.index(row, 0, parent)
            if not parent.isValid():
                return QModelIndex()

        return parent

    def mimeData(self, indexes, /):
        mime = QMimeData()
        encoded = QByteArray()
        stream = QDataStream(encoded, QIODevice.OpenModeFlag.WriteOnly)

        if not indexes:
            return mime

        index = indexes[0]
        if index is None:
            return mime

        parent_index = index.parent()
        parent_path = self.path_from_index(parent_index)
        source_row = index.row()

        stream.writeInt32(len(parent_path))
        for r in parent_path:
            stream.writeInt32(r)
        stream.writeInt32(source_row)

        mime.setData('application/x-xml-object-model-item', encoded)
        return mime

    def dropMimeData(self, data, action, row, column, parent, /) -> bool:
        if action == Qt.DropAction.IgnoreAction:
            return True

        if action != Qt.DropAction.MoveAction:
            return False

        if not data.hasFormat('application/x-xml-object-model-item'):
            return False

        encoded = data.data('application/x-xml-object-model-item')
        stream = QDataStream(encoded, QIODevice.OpenModeFlag.ReadOnly)
        n = stream.readInt32()
        parent_path = [stream.readInt32() for _ in range(n)]
        source_row = stream.readInt32()

        source_parent = self.index_from_path(parent_path)

        if row == -1:
            row = self.rowCount(parent)

        ok = self.moveRows(source_parent, source_row, 1, parent, row)
        self._ignore_remove = ok
        return ok

    def moveRows(self, source_parent: QModelIndex, source_row: int, count: int, destination_parent: QModelIndex | QPersistentModelIndex,
                 destination_child: int, /):
        if count != 1:
            return False

        if source_parent == destination_parent and destination_child in (source_row, source_row + 1):
            return False

        if not self.validate_move(source_parent, source_row, destination_parent, destination_child):
            return False

        source_parent_item = self.item_from_index(source_parent)
        destination_parent_item = self.item_from_index(destination_parent)

        self.beginMoveRows(source_parent, source_row, source_row, destination_parent, destination_child)

        if source_parent == destination_parent and destination_child > source_row:
            destination_child -= 1

        moved_item = source_parent_item._pop_child(source_row)
        destination_parent_item._insert_child(destination_child, moved_item)

        self.endMoveRows()
        return True

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
        if self._ignore_remove:
            self._ignore_remove = False
            return True

        parent_item = self.item_from_index(parent)

        if count <= 0:
            return False

        if row < 0 or row + count > parent_item.row_count():
            return False

        self.beginRemoveRows(parent, row, row + count - 1)
        for child in parent_item.item_children[row:row + count]:
            child.item_parent = None
            child.model = None
        del parent_item.item_children[row:row + count]
        self.endRemoveRows()

        return True

    def remove_rows_from_item(self, row: int, count: int, parent: XmlObjectModelItem | None = None) -> bool:
        return self.removeRows(row, count, self.index_from_item(parent))

    @abstractmethod
    def validate_move(self, source_parent: QModelIndex, source_row: int, destination_parent: QModelIndex | QPersistentModelIndex, destination_child: int) -> bool:
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