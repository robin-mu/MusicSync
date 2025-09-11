from dataclasses import dataclass, field
import xml.etree.ElementTree as et
from typing import Union
from xml.etree.ElementTree import Element


@dataclass
class MusicSyncLibrary:
    metadata_table_path: str = ''
    children: list[Union['Folder', 'Collection']] = field(default_factory=list)

    @staticmethod
    def read_xml(xml_path: str) -> 'MusicSyncLibrary':
        tree = et.parse(xml_path)
        root = tree.getroot()
        children = []
        for child in root:
            if child.tag == 'Folder':
                children.append(Folder.from_xml(child))
            elif child.tag == 'Collection':
                children.append(Collection.from_xml(child))

        return MusicSyncLibrary(children=children, **root.attrib)

    def write_xml(self, xml_path: str):
        attrs = vars(self).copy()
        attrs.pop('children')

        root = et.Element('MusicSyncLibrary', **attrs)
        for child in self.children:
            root.append(child.to_xml())

        et.ElementTree(root).write(xml_path)


@dataclass
class Folder:
    name: str
    children: list[Union['Folder', 'Collection']] = field(default_factory=list)

    @staticmethod
    def from_xml(el: Element) -> 'Folder':
        children = []
        for child in el:
            if child.tag == 'Folder':
                children.append(Folder.from_xml(child))
            elif child.tag == 'Collection':
                children.append(Collection.from_xml(child))

        return Folder(children=children, **el.attrib)

    def to_xml(self) -> Element:
        attrs = vars(self).copy()
        attrs.pop('children')

        el = et.Element('Folder', **attrs)
        for child in self.children:
            el.append(child.to_xml())
        return el

@dataclass
class Collection:
    name: str
    folder_path: str = ''
    filename_format: str = ''
    file_extension: str = ''
    file_tags: str = ''
    save_playlists_to_subfolders: bool = False
    urls: list['CollectionUrl'] = field(default_factory=list)

    def __post_init__(self):
        if isinstance(self.save_playlists_to_subfolders, str):
            self.save_playlists_to_subfolders = self.save_playlists_to_subfolders == 'True'

    @staticmethod
    def from_xml(el: Element) -> 'Collection':
        urls = []
        for child in el:
            if child.tag == 'CollectionUrl':
                urls.append(CollectionUrl.from_xml(child))

        return Collection(urls=urls, **el.attrib)

    def to_xml(self) -> Element:
        attrs = vars(self).copy()
        attrs.pop('urls')
        attrs['save_playlists_to_subfolders'] = str(self.save_playlists_to_subfolders)

        el = et.Element('Collection', **attrs)
        for url in self.urls:
            el.append(url.to_xml())
        return el


@dataclass
class CollectionUrl:
    url: str
    name: str = ''
    tracks: list[str] = field(default_factory=list)

    @staticmethod
    def from_xml(el: Element) -> 'CollectionUrl':
        tracks = []
        for child in el:
            if child.tag == 'Track':
                tracks.append(child.text)
        return CollectionUrl(**el.attrib)

    def to_xml(self) -> Element:
        attrs = vars(self).copy()
        attrs.pop('tracks')

        el = et.Element('CollectionUrl', **attrs)
        for track in self.tracks:
            track_el = et.Element('Track')
            track_el.text = track
            el.append(track_el)
        return el