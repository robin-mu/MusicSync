import typing
from xml.etree import ElementTree

from PySide6 import QtCore
from PySide6.QtGui import QStandardItem, QStandardItemModel

from src.xml_object import XmlObject


class XmlObjectModelItem(QStandardItem):
    def __init__(self):
        super().__init__()

    def to_xml_object(self) -> 'XmlObject':
        raise NotImplementedError

    @staticmethod
    def from_xml_object(object: 'XmlObject') -> 'XmlObjectModelItem':
        raise NotImplementedError


class XmlObjectModel(QStandardItemModel):
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

    @classmethod
    def item_from_xml(cls, el: ElementTree.Element) -> 'XmlObjectModelItem':
        raise NotImplementedError

    @classmethod
    def validate_drop(cls, parent_item: XmlObjectModelItem | None, item: XmlObjectModelItem) -> bool:
        raise NotImplementedError
