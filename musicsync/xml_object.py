from abc import abstractmethod, ABC
from xml.etree.ElementTree import Element


class XmlObject(ABC):
    @staticmethod
    @abstractmethod
    def from_xml(el: Element) -> 'XmlObject':
        pass

    @abstractmethod
    def to_xml(self) -> Element:
        pass
