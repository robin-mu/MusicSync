from xml.etree.ElementTree import Element


class XmlObject:
    @staticmethod
    def from_xml(el: Element) -> 'XmlObject':
        raise NotImplementedError()

    def to_xml(self) -> Element:
        raise NotImplementedError()