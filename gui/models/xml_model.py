import typing
from abc import abstractmethod, ABC, ABCMeta
from xml.etree import ElementTree

from PySide6 import QtCore
from PySide6.QtGui import QStandardItem, QStandardItemModel

from musicsync.xml_object import XmlObject

QStandardItemMeta = type(QStandardItem)
class _ABCQStandardItemMeta(QStandardItemMeta, ABCMeta):
    pass

QStandardItemModelMeta = type(QStandardItemModel)
class _ABCQStandardItemModelMeta(QStandardItemModelMeta, ABCMeta):
    pass

class XmlObjectModelItem(QStandardItem, ABC, metaclass=_ABCQStandardItemMeta):
    def __init__(self):
        super().__init__()

    @abstractmethod
    def to_xml_object(self) -> 'XmlObject':
        pass

    @staticmethod
    @abstractmethod
    def from_xml_object(xml_object: 'XmlObject') -> 'XmlObjectModelItem':
        pass


class XmlObjectModel(QStandardItemModel, ABC, metaclass=_ABCQStandardItemModelMeta):
    """
    A QStandardItemModel whose items are ``XmlObjectModelItem``s.
    """

    def __init__(self):
        super(XmlObjectModel, self).__init__()

    def mimeTypes(self, /):
        return ['application/xml']

    def mimeData(self, indexes):
        if not indexes:
            return None

        item = typing.cast(XmlObjectModelItem, self.itemFromIndex(indexes[0]))
        mime_data = QtCore.QMimeData()
        mime_data.setData('application/xml', ElementTree.tostring(item.to_xml_object().to_xml()))
        return mime_data

    def dropMimeData(self, data, action, row, column, parent, /):
        if not data.hasFormat('application/xml'):
            return False

        xml_data = ElementTree.fromstring(data.data('application/xml').data())
        item = self.item_from_xml(xml_data)

        parent_item = self.itemFromIndex(parent) if parent and parent.isValid() else None
        if not self.validate_drop(parent_item, item):
            return False

        if parent_item:
            if row >= 0:
                parent_item.insertRow(row, [item])
            else:
                parent_item.appendRow(item)
        elif row >= 0:
            self.insertRow(row, item)
        else:
            self.appendRow(item)

        return True

    @staticmethod
    @abstractmethod
    def item_from_xml(el: ElementTree.Element) -> 'XmlObjectModelItem':
        pass

    @staticmethod
    @abstractmethod
    def validate_drop(parent_item: XmlObjectModelItem | None, item: XmlObjectModelItem) -> bool:
        pass
