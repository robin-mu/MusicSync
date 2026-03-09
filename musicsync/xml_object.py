from abc import abstractmethod, ABC
from typing import Self
from xml.etree.ElementTree import Element


class XmlObject(ABC):
    @classmethod
    @abstractmethod
    def from_xml(cls, el: Element) -> Self:
        pass

    @abstractmethod
    def to_xml(self) -> Element:
        pass
