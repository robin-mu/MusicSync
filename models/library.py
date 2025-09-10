import xml.etree.ElementTree as et
from xml.etree.ElementTree import Element

from PySide6.QtGui import QStandardItemModel, QStandardItem


class Folder(QStandardItem):
    def __init__(self, name):
        super().__init__()
        self.setText(name)

    def to_element(self):
        return et.Element("Folder", name=self.text())


class Collection(QStandardItem):
    def __init__(self, name: str, folder_path: str='', filename_format: str='', file_extension: str='',
                 file_tags: str= '', save_playlists_to_subfolders: bool=False):
        super().__init__()

        self.setText(name)

        self.folder_path = folder_path
        self.filename_format = filename_format
        self.file_extension = file_extension
        self.file_tags = file_tags.split(',')

        if isinstance(save_playlists_to_subfolders, str):
            self.save_playlists_to_subfolders = save_playlists_to_subfolders == 'True'
        else:
            self.save_playlists_to_subfolders = save_playlists_to_subfolders

    def to_element(self):
        return et.Element("Collection", name=self.text(), folder_path=self.folder_path,
                          filename_format=self.filename_format, file_extension=self.file_extension,
                          file_tags=','.join(self.file_tags),
                          save_playlists_to_subfolders=str(self.save_playlists_to_subfolders))


class CollectionUrl(QStandardItem):
    def __init__(self, url: str, name: str='', tracks: list[str]=None):
        super().__init__()
        self.url: str = url
        if not name:
            f = self.font()
            f.setItalic(True)
            self.setFont(f)

            self.setEditable(False)

            name = url

        self.setText(name)
        self.tracks: list[str] = [] if tracks is None else tracks

    def set_name(self, name: str):
        self.setText(name)
        f = self.font()
        f.setItalic(False)
        self.setFont(f)
        self.setEditable(True)

    def to_element(self):
        name = self.text() if self.text() != self.url else ''
        url_element = et.Element("CollectionUrl", name=name, url=self.url)
        for track in self.tracks:
            url_element.append(et.Element("Track", url=track))
        return url_element


class LibraryModel(QStandardItemModel):
    def __init__(self, xml_path: str=None, track_table_path: str=''):
        super(LibraryModel, self).__init__()

        self.root = self.invisibleRootItem()
        self.track_table_path = track_table_path

        if xml_path is not None:
            tree = et.parse(xml_path)
            xml_root = tree.getroot()
            self.build_tree(self.root, xml_root)

    def build_tree(self, parent: QStandardItem, children: Element):
        for child in children:
            if child.tag == 'Folder':
                new_folder = Folder(child.attrib['name'])
                parent.appendRow(new_folder)
                self.build_tree(new_folder, child)
            elif child.tag == 'Collection':
                new_collection = Collection(**child.attrib)
                parent.appendRow(new_collection)
                for url in child:
                    self.add_url(new_collection, url.attrib['url'], url.attrib['name'], [track.attrib['url'] for track in url])

    def to_xml(self, filename):
        xml_root = et.Element('MusicSyncLibrary')

        def append(parent: Element, children: QStandardItem):
            for i in range(children.rowCount()):
                row = children.child(i)

                new_element = row.to_element()
                append(new_element, row)
                parent.append(new_element)

        append(xml_root, self.root)
        et.ElementTree(xml_root).write(filename)

    @staticmethod
    def add_folder(parent: Folder):
        new_folder = Folder('')
        parent.appendRow(new_folder)
        return new_folder

    @staticmethod
    def add_collection(parent: Folder):
        new_collection = Collection('')
        parent.appendRow(new_collection)
        return new_collection

    @staticmethod
    def add_url(parent: Collection, url: str, name: str= '', tracks=None):
        new_url = CollectionUrl(url, name, tracks)
        parent.appendRow(new_url)
        return new_url